import os
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import os
import aiofiles
import logging
import traceback

from backend.app.config import settings
from backend.app.database import get_db, AsyncSessionLocal
from backend.app.models.user import User
from backend.app.models.document import Document, DocumentChunk
from backend.app.schemas.document import DocumentResponse, DocumentChunkResponse, DocumentUploadResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.acl_service import check_document_access, check_collection_access, get_permitted_document_ids
from backend.app.services.pdf_parser import validate_pdf_file, compute_file_hash, extract_metadata_and_chunks
from backend.app.services.embedding_service import embedding_service
from backend.app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

os.makedirs(settings.STORAGE_DIR, exist_ok=True)

async def _process_pdf_background(doc_id: str, file_bytes: bytes, user_id: str, collection_id: str, filename: str):
    """
    Background worker that runs PyMuPDF extraction, batch embedding, and DB insertion,
    updating document status along the way (parsing -> indexing -> ready).
    """
    async with AsyncSessionLocal() as bg_db:
        try:
            # Stage 1: Parse PDF
            pdf_info, chunks_data = extract_metadata_and_chunks(file_bytes)
            
            doc_res = await bg_db.execute(select(Document).where(Document.id == doc_id))
            doc = doc_res.scalars().first()
            if not doc:
                return

            doc.page_count = pdf_info.get("page_count", 0)
            if pdf_info.get("title") and (not doc.title or doc.title == doc.filename):
                doc.title = pdf_info["title"]
            if pdf_info.get("authors") and not doc.authors:
                doc.authors = pdf_info["authors"]
            doc.upload_status = "indexing"
            await bg_db.commit()

            # Stage 2: Batched embedding generation
            chunk_texts = [c["content"] for c in chunks_data]
            chunk_embeddings = embedding_service.embed_batch(chunk_texts, batch_size=64)

            # Stage 3: Bulk insert document chunks
            for i, chunk in enumerate(chunks_data):
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    page_number=chunk["page_number"],
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    bounding_box=chunk["bounding_box"],
                    embedding=chunk_embeddings[i] if i < len(chunk_embeddings) else None
                )
                bg_db.add(chunk_obj)

            # Stage 4: Mark ready
            doc.upload_status = "ready"
            await bg_db.commit()

            # Audit log
            await log_audit_event(
                db=bg_db,
                action_type="DOC_INDEXED",
                user_id=user_id,
                resource_id=doc.id,
                details={
                    "filename": filename,
                    "collection_id": collection_id,
                    "page_count": doc.page_count,
                    "chunks_count": len(chunks_data)
                }
            )
        except Exception as e:
            logger.error(f"Error during background PDF processing for {doc_id}: {e}")
            traceback.print_exc()
            try:
                doc_res = await bg_db.execute(select(Document).where(Document.id == doc_id))
                doc = doc_res.scalars().first()
                if doc:
                    doc.upload_status = "failed"
                    await bg_db.commit()
            except Exception:
                pass

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    collection_id: str = Form(...),
    title: Optional[str] = Form(None),
    background: bool = Form(False),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and parse PDF document into a collection.
    Requires role 'reviewer' or 'owner'. Viewers cannot upload.
    When background=True, returns immediately with status 'parsing' while background worker indexes passages.
    """
    # 1. Enforce Collection ACL (Requires Reviewer or Owner)
    collection = await check_collection_access(db, current_user.id, collection_id, required_role="reviewer")

    # 2. Read and validate file bytes
    file_bytes = await file.read()
    validate_pdf_file(filename=file.filename, file_bytes=file_bytes, content_type=file.content_type)
    file_hash = compute_file_hash(file_bytes)

    # 3. Check for duplicates in collection
    existing_doc = await db.execute(
        select(Document).where(
            Document.collection_id == collection_id,
            Document.file_hash == file_hash
        )
    )
    if existing_doc.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with identical content has already been uploaded to this collection."
        )

    # 4. Save file to disk storage
    saved_filename = f"{file_hash[:16]}_{file.filename}"
    file_path = os.path.join(settings.STORAGE_DIR, saved_filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    if background:
        # Non-blocking background ingestion
        doc_record = Document(
            collection_id=collection_id,
            title=title or file.filename,
            authors="Analyzing...",
            filename=file.filename,
            file_path=file_path,
            file_hash=file_hash,
            file_size_bytes=len(file_bytes),
            page_count=0,
            upload_status="parsing",
            uploaded_by=current_user.id
        )
        db.add(doc_record)
        await db.commit()
        await db.refresh(doc_record)

        background_tasks.add_task(
            _process_pdf_background,
            doc_record.id,
            file_bytes,
            current_user.id,
            collection_id,
            file.filename
        )

        return DocumentUploadResponse(
            document=DocumentResponse.model_validate(doc_record),
            chunks_created=0,
            message="Document uploaded successfully. Processing passages in background."
        )

    # Synchronous ingestion (for instant test validation or CLI callers)
    pdf_info, chunks_data = extract_metadata_and_chunks(file_bytes)
    doc_record = Document(
        collection_id=collection_id,
        title=title or pdf_info.get("title") or file.filename,
        authors=pdf_info.get("authors") or "Unknown Author",
        filename=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        file_size_bytes=len(file_bytes),
        page_count=pdf_info.get("page_count", 0),
        upload_status="ready",
        uploaded_by=current_user.id
    )
    db.add(doc_record)
    await db.commit()
    await db.refresh(doc_record)

    chunk_texts = [chunk["content"] for chunk in chunks_data]
    chunk_embeddings = embedding_service.embed_batch(chunk_texts, batch_size=64)

    for i, chunk in enumerate(chunks_data):
        chunk_obj = DocumentChunk(
            document_id=doc_record.id,
            page_number=chunk["page_number"],
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            bounding_box=chunk["bounding_box"],
            embedding=chunk_embeddings[i] if i < len(chunk_embeddings) else None
        )
        db.add(chunk_obj)
    await db.commit()
    await db.refresh(doc_record)

    # Audit log event
    await log_audit_event(
        db=db,
        action_type="DOC_UPLOAD",
        user_id=current_user.id,
        resource_id=doc_record.id,
        details={
            "filename": file.filename,
            "collection_id": collection_id,
            "page_count": doc_record.page_count,
            "chunks_count": len(chunks_data)
        },
        ip_address=request.client.host if request.client else None
    )

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(doc_record),
        chunks_created=len(chunks_data),
        message="Document uploaded and indexed successfully."
    )

@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns document processing status (parsing -> indexing -> ready / failed).
    """
    doc = await check_document_access(db, current_user.id, document_id, required_level="view")
    return {
        "id": doc.id,
        "upload_status": doc.upload_status,
        "page_count": doc.page_count,
        "title": doc.title,
        "filename": doc.filename,
        "authors": doc.authors
    }

@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    collection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns only documents the current user has permission to view.
    Enforced BEFORE retrieval using permitted document IDs.
    """
    permitted_doc_ids = await get_permitted_document_ids(db, current_user.id, collection_id)
    if not permitted_doc_ids:
        return []

    query = select(Document).where(Document.id.in_(permitted_doc_ids))
    res = await db.execute(query)
    docs = res.scalars().all()
    return [DocumentResponse.model_validate(d) for d in docs]

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches document metadata after strict ACL check.
    """
    doc = await check_document_access(db, current_user.id, document_id, required_level="view")
    return DocumentResponse.model_validate(doc)

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
async def get_document_chunks(
    document_id: str,
    page: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves passage chunks with coordinates for a document or specific page.
    Enforces server-side ACL before reading passages.
    """
    await check_document_access(db, current_user.id, document_id, required_level="view")

    query = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    if page is not None:
        query = query.where(DocumentChunk.page_number == page)

    query = query.order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
    res = await db.execute(query)
    chunks = res.scalars().all()
    return [DocumentChunkResponse.model_validate(c) for c in chunks]

@router.get("/{document_id}/file")
async def stream_document_file(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Streams raw PDF file. Negative access test will reject unauthorized users with 403 Forbidden.
    """
    doc = await check_document_access(db, current_user.id, document_id, required_level="view")
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File on storage volume not found.")

    return FileResponse(
        path=doc.file_path,
        media_type="application/pdf",
        filename=doc.filename
    )

from pydantic import BaseModel

class DocumentPermissionCreate(BaseModel):
    user_email: str
    permission_level: str = "view"

@router.post("/{document_id}/permissions")
async def grant_document_permission(
    document_id: str,
    payload: DocumentPermissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Grants explicit document permission to a collaborator by email.
    Requires owner or reviewer role on the document.
    """
    doc = await check_document_access(db, current_user.id, document_id, required_level="review")
    
    # Lookup target user
    user_res = await db.execute(select(User).where(User.email == payload.user_email))
    target_user = user_res.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User with email '{payload.user_email}' not found.")

    from backend.app.models.document import DocumentPermission
    perm = DocumentPermission(
        document_id=document_id,
        user_id=target_user.id,
        permission_level=payload.permission_level
    )
    db.add(perm)
    await db.commit()
    await db.refresh(perm)

    await log_audit_event(
        db=db,
        action_type="GRANT_DOCUMENT_PERMISSION",
        user_id=current_user.id,
        resource_id=document_id,
        details={"granted_to": target_user.id, "permission_level": payload.permission_level}
    )

    return {"message": "Permission granted successfully", "permission_id": perm.id}

