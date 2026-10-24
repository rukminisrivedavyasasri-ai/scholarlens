from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class ExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    field_name: str
    field_value: str
    is_unavailable: bool = False
    unavailable_reason: Optional[str] = None
    confidence: float
    page_number: Optional[int] = None
    passage_excerpt: Optional[str] = None
    review_status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

class ExtractionUpdateRequest(BaseModel):
    field_value: Optional[str] = None
    review_status: str = Field(..., description="'approved', 'edited', or 'rejected'")

class ClaimVerifyRequest(BaseModel):
    claim_text: str = Field(..., min_length=3)
    document_id: str
    page_number: int
    cited_excerpt: Optional[str] = None

class ClaimVerifyResponse(BaseModel):
    claim: str
    status: str  # supported, partially_supported, unsupported
    status_label: str
    confidence: float
    reasoning: str
    valid_citation: bool
    similarity_score: Optional[float] = None
