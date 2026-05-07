from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI

from .config import settings
from .consumer import poll_forever

consumer_thread: Thread | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global consumer_thread
    consumer_thread = Thread(target=poll_forever, daemon=True)
    consumer_thread.start()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


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
