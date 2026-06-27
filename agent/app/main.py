import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .authorization import ANONYMOUS_USER_ID
from .config import settings
from .consumer import poll_forever
from .governance_store import get_store
from .logging_config import configure_logging
from .models import PromptEvent
from .workflow import build_response

consumer_thread: Thread | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global consumer_thread
    configure_logging()
    consumer_thread = Thread(target=poll_forever, daemon=True)
    consumer_thread.start()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    user_id: str = ANONYMOUS_USER_ID


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready")
def ready() -> dict[str, object]:
    consumer_alive = consumer_thread is not None and consumer_thread.is_alive()
    return {
        "status": "ready" if consumer_alive else "degraded",
        "service": settings.app_name,
        "prompt_topic": settings.prompt_topic,
        "consumer_alive": consumer_alive,
    }


@app.get("/employees")
def employees() -> list[dict]:
    """Directory listing used by the dashboard's user picker. Returns synthetic
    seed data only — no real PII."""
    return [
        {
            "employee_id": e["employee_id"],
            "name": f"{e['first_name']} {e['last_name']}",
            "title": e["title"],
            "clearance_level": e["clearance_level"],
        }
        for e in get_store().list_employees()
    ]


@app.get("/metrics/latency")
def latency_metrics() -> dict:
    """Return P50 / P95 / P99 agent latency from persisted request_metrics."""
    return get_store().get_latency_percentiles()


@app.post("/query")
def query(req: QueryRequest) -> dict:
    """Synchronous prompt → response path that bypasses Kafka.

    Intended for the dashboard and local testing — production traffic still
    flows gateway → Kafka → consumer.
    """
    request_id = str(uuid.uuid4())
    event = PromptEvent(
        request_id=request_id,
        user_id=req.user_id,
        prompt=req.prompt,
        sanitized_prompt=req.prompt,
        redaction_count=0,
        policy_tags=[],
        created_at=datetime.now(UTC),
    )
    started = time.perf_counter()
    response = build_response(event, agent_latency_ms=None)  # latency captured below
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    # Patch the metrics row with the actual measured latency.
    # build_response already wrote a row; we update it here so the timing
    # is measured outside the graph rather than inside it.
    try:
        get_store().write_request_metrics(
            request_id=request_id,
            agent_latency_ms=round(elapsed_ms, 2),
        )
    except Exception:
        pass  # non-fatal — response is already built
    return {
        "request_id": response.request_id,
        "answer": response.answer,
        "reasoning_trace": response.reasoning_trace,
        "sources": response.sources,
        "verification": response.verification,
        "latency_ms": round(elapsed_ms, 1),
        "created_at": response.created_at.isoformat(),
    }
