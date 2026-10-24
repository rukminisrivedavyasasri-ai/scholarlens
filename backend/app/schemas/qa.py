from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Research query or search terms")
    collection_id: Optional[str] = Field(None, description="Optional collection scope")
    top_k: int = Field(5, ge=1, le=50, description="Max passages to return")

class PassageResult(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    page_number: int
    chunk_index: int
    content: str
    bounding_box: Optional[Dict[str, Any]] = None
    score: float

class CitationItem(BaseModel):
    document_id: str
    document_title: str
    page_number: int
    chunk_id: Optional[str] = None
    excerpt: str
    score: float

class QARequest(BaseModel):
    query: str = Field(..., min_length=2, description="Research inquiry question")
    collection_id: Optional[str] = Field(None, description="Optional collection scope")
    mode: str = Field("grounded_verified", description="'grounded_verified' or 'baseline_rag'")

class QAResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationItem] = []
    mode: str
    abstention: bool = False
