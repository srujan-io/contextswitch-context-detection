from typing import Any
from pydantic import BaseModel, Field

class DispatchRequest(BaseModel):
    tab_id: int
    plan: dict[str, Any]
    context: dict[str, Any]
    user_approved: bool = False

class ExecutionResultRequest(BaseModel):
    action_id: str = Field(min_length=1)
    tab_id: int
    status: str
    verified: bool = False
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
