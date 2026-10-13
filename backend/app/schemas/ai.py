"""AI chat schemas (spec #31, #32, #93)."""

from typing import Any

from pydantic import BaseModel, Field


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    image: str | None = Field(
        default=None,
        max_length=5_000_000,
        description="Optional data URL (data:image/...;base64,...) for vision models",
    )


class AiProposal(BaseModel):
    """A pending action that requires user confirmation (spec #33, #69, #93).

    WRITE/DESTRUCTIVE tool calls are never executed directly — the agent
    returns them as proposals so the user can Save / Edit / Cancel via the UI.
    """

    id: str
    action: str
    record_type: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class AiChatResponse(BaseModel):
    reply: str = ""
    proposals: list[AiProposal] = Field(default_factory=list)
