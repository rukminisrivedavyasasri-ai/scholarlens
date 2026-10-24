import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from backend.app.database import Base

class EvidenceBoardItem(Base):
    __tablename__ = "evidence_board_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    claim = Column(Text, nullable=False)
    citation_excerpt = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    
    # Evidence validation status: supported, partially_supported, unsupported, conflicting, not_directly_comparable
    evidence_status = Column(String(50), default="supported")
    
    # Board review state: proposed (pending), approved, rejected
    board_status = Column(String(50), default="proposed")
    previous_status = Column(String(50), nullable=True)  # For undo
    
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
