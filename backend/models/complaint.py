import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from db.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String(10), nullable=False)          # WATER | AIR | WASTE
    scope = Column(String(10), nullable=False)              # CAMPUS | CITY
    issue_summary = Column(String(255), nullable=False)
    location = Column(Text, nullable=False)
    duration = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    previous_action = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="OPEN")
    routed_to = Column(String(100), nullable=False)         # simulated authority
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
