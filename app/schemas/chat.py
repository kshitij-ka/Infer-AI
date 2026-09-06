"""
Request and response models for the chat route.
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """The submitted question. Limited to 4000 characters."""

    question: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """The answer and the metrics recorded for this specific request."""

    answer: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
