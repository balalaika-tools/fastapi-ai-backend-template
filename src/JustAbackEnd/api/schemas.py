from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
from datetime import datetime


class ChatCompletionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChatCompletionResponse(BaseModel):
    response: str
    session_id: str


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    python_version: str
    platform: str
    services: Dict[str, bool] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[Any] = None
