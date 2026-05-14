"""Pydantic models for the SHL Assessment Recommender API."""
from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in the conversation."""
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    messages: list[Message] = Field(..., min_length=1)


class Recommendation(BaseModel):
    """A single assessment recommendation."""
    name: str
    url: str
    test_type: str


class ChatResponse(BaseModel):
    """Response body for POST /chat."""
    reply: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    end_of_conversation: bool = False
