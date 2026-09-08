from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.enums import CategoryType, ScopeType
from db.database import get_db
from schemas.chat import ChatRequest, ChatResponse
from schemas.complaint import ComplaintRequest
from services.complaint_service import complaint_service
from services.conversation_service import conversation_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """
    Process one turn of conversation.

    The conversation state machine in ConversationService advances the phase
    and returns an appropriate response. If the user has confirmed a complaint,
    the sentinel message '__SUBMIT_COMPLAINT__' is replaced with the actual
    complaint registration result from ComplaintService.
    """
    response = conversation_service.process_message(request)

    # Handle the complaint submission sentinel
    if response.message == "__SUBMIT_COMPLAINT__" and response.complaint_draft:
        draft = response.complaint_draft
        cls = response.classification

        # Build a ComplaintRequest from the collected draft fields
        try:
            complaint_req = ComplaintRequest(
                session_id=request.session_id,
                category=CategoryType(draft.get("category", "WASTE")),
                scope=ScopeType(draft.get("scope", "CITY")),
                issue_summary=draft.get("issue_summary", "Issue reported via CivicAI")[:255],
                location=draft.get("location", "Not specified"),
                duration=draft.get("duration"),
                description=draft.get("description"),
                previous_action=draft.get("previous_action"),
                confirmed=True,
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid complaint data: {exc}") from exc

        complaint_response = complaint_service.register(complaint_req, db)

        return ChatResponse(
            session_id=response.session_id,
            message=complaint_response.message,
            classification=cls,
            requires_confirmation=False,
            complaint_draft=None,
            phase=response.phase,
        )

    return response
