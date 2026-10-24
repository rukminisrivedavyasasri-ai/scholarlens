import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime
from backend.app.database import Base

class ExtractedDetail(Base):
    __tablename__ = "extracted_details"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(50), nullable=False)  # objective, methodology, population, findings, limitations
    field_value = Column(Text, nullable=False)
    is_unavailable = Column(Boolean, default=False)
    unavailable_reason = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    page_number = Column(Integer, nullable=True)
    passage_excerpt = Column(Text, nullable=True)
    review_status = Column(String(50), default="proposed")  # proposed, approved, edited, rejected, unavailable
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
