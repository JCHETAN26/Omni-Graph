import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .consumer import poll_forever
from .models import PromptEvent
from .workflow import build_response

consumer_thread: Thread | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global consumer_thread
    consumer_thread = Thread(target=poll_forever, daemon=True)
    consumer_thread.start()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    user_id: str = "dashboard-local"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "service": settings.app_name,
        "prompt_topic": settings.prompt_topic,
    }


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
    response = build_response(event)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "request_id": response.request_id,
        "answer": response.answer,
        "reasoning_trace": response.reasoning_trace,
        "sources": response.sources,
        "verification": response.verification,
        "latency_ms": round(elapsed_ms, 1),
        "created_at": response.created_at.isoformat(),
    }
