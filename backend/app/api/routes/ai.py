"""AI chat endpoints (spec #31, #32, #79, #93).

``POST /ai/chat``      — non-streaming (returns full response)
``POST /ai/chat/stream`` — NDJSON streaming (text deltas + proposals)
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_ai_agent_service, get_audit_service, get_current_user
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.ai import AiChatRequest, AiChatResponse
from app.services.ai_agent import AiAgentService, AINotConfiguredError
from app.services.audit import AuditService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AiChatResponse)
async def chat(
    payload: AiChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AiAgentService = Depends(get_ai_agent_service),
    audit: AuditService = Depends(get_audit_service),
) -> AiChatResponse:
    try:
        result = await service.chat(
            user_id=current_user.id,
            message=payload.message,
            image=payload.image,
            user_display=current_user.display_name or current_user.username,
            locale=current_user.locale,
        )
    except AINotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI is not configured. Configure an LLM provider in Settings → AI.",
        ) from None
    audit.log(
        action=AuditAction.AI_ACTION,
        user_id=current_user.id,
        resource_type="ai_chat",
        resource_id=None,
        meta={
            "proposals": len(result.proposals),
            "reply_len": len(result.reply),
        },
        request=request,
    )
    return result


@router.post("/chat/stream")
async def chat_stream(
    payload: AiChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AiAgentService = Depends(get_ai_agent_service),
    audit: AuditService = Depends(get_audit_service),
) -> StreamingResponse:
    """Stream AI chat as NDJSON (one JSON object per line).

    Events:
    - ``{"type":"text","content":"..."}``    — partial text
    - ``{"type":"proposals","proposals":[...]}`` — proposals
    - ``{"type":"done"}``                     — stream complete
    - ``{"type":"error","message":"..."}``    — error
    """

    async def generate():
        proposal_count = 0
        reply_len = 0
        try:
            async for event in service.chat_stream(
                user_id=current_user.id,
                message=payload.message,
                image=payload.image,
                user_display=current_user.display_name or current_user.username,
                locale=current_user.locale,
            ):
                if event["type"] == "proposals":
                    proposal_count = len(event.get("proposals", []))
                elif event["type"] == "text":
                    reply_len += len(event.get("content", ""))
                yield json.dumps(event, ensure_ascii=False, default=str) + "\n"
        except AINotConfiguredError:
            yield (
                json.dumps({"type": "error", "message": "AI is not configured"}, ensure_ascii=False)
                + "\n"
            )
        finally:
            audit.log(
                action=AuditAction.AI_ACTION,
                user_id=current_user.id,
                resource_type="ai_chat_stream",
                resource_id=None,
                meta={
                    "proposals": proposal_count,
                    "reply_len": reply_len,
                },
                request=request,
            )

    return StreamingResponse(generate(), media_type="application/x-ndjson")
