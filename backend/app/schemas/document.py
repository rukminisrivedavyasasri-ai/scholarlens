from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    user_role: Optional[str] = "viewer"

class CollectionMemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

class CollectionMemberInvite(BaseModel):
    email: str
    role: str = "viewer"  # reviewer, viewer

class CollectionMemberUpdate(BaseModel):
    role: str

class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    page_number: int
    chunk_index: int
    content: str
    bounding_box: Optional[Dict[str, Any]] = None

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    collection_id: str
    title: str
    authors: Optional[str] = None
    year: Optional[int] = None
    filename: str
    file_size_bytes: int
    page_count: int
    upload_status: str
    created_at: datetime

class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    chunks_created: int
    message: str
