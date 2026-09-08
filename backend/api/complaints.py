from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.complaint import ComplaintRequest, ComplaintResponse, ComplaintStatusResponse
from services.complaint_service import complaint_service

router = APIRouter(prefix="/api", tags=["complaints"])


@router.post("/complaints", response_model=ComplaintResponse)
async def register_complaint(
    request: ComplaintRequest,
    db: Session = Depends(get_db),
) -> ComplaintResponse:
    """
    Register a confirmed complaint.
    The 'confirmed' field must be True — complaints cannot be submitted without
    explicit user confirmation (Responsible AI: human oversight principle).
    """
    if not request.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Complaint cannot be submitted without explicit user confirmation (confirmed=true).",
        )
    return complaint_service.register(request, db)


@router.get("/complaints/{complaint_id}", response_model=ComplaintStatusResponse)
async def get_complaint_status(
    complaint_id: str,
    db: Session = Depends(get_db),
) -> ComplaintStatusResponse:
    """
    Retrieve the status of a simulated complaint by its ID.
    """
    result = complaint_service.get_status(complaint_id, db)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complaint '{complaint_id}' not found.",
        )
    return result
