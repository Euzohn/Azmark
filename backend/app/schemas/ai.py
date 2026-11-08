"""AI chat schemas (spec #31, #32, #93)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AiHistoryProposalOutcome(BaseModel):
    """What happened to a proposal the assistant raised in a prior turn.

    The assistant itself can't see whether the user saved or cancelled a
    proposal (it has no memory across requests), so the client relays the
    outcome back as part of the conversation history (spec #69).
    """

    action: str
    record_type: str
    summary: str = Field(max_length=400)
    status: Literal["pending", "saved", "cancelled", "duplicate"]


class AiHistoryMessage(BaseModel):
    """One turn of prior conversation, sent back by the client for context.

    The client owns the chat history (stored locally); the backend is
    stateless. Content is capped so a runaway local history cannot blow up the
    request payload, and each entry is treated as untrusted user content
    (spec #70).
    """

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)
    proposals: list[AiHistoryProposalOutcome] | None = None
    #: Chain of thought from a prior assistant turn. DeepSeek requires it to be
    #: echoed back when tools are in play, so it round-trips through the client.
    reasoning: str | None = Field(default=None, max_length=20000)


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    image: str | None = Field(
        default=None,
        max_length=5_000_000,
        description="Optional data URL (data:image/...;base64,...) for vision models",
    )
    history: list[AiHistoryMessage] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Prior conversation turns (most recent last). Lets the assistant "
            "follow up on earlier proposals and their saved/cancelled outcomes."
        ),
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
    #: Chain of thought for the final turn (streaming path emits it as deltas).
    reasoning: str = ""
