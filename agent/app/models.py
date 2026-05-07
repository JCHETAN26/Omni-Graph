from datetime import datetime
from typing import Any, List

from pydantic import BaseModel


class PromptEvent(BaseModel):
    request_id: str
    user_id: str
    prompt: str
    sanitized_prompt: str
    redaction_count: int
    policy_tags: List[str] = []
    created_at: datetime


class AgentResponse(BaseModel):
    request_id: str
    answer: str
    reasoning_trace: List[str]
    created_at: datetime
    sources: List[dict[str, Any]] = []
