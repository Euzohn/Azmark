"""AI chat endpoint (spec #31, #32, #79, #93)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
