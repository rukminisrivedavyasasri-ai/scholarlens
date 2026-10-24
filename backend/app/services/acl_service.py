from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from fastapi import HTTPException, status

from backend.app.models.workspace import Workspace, WorkspaceMember, Collection
from backend.app.models.document import Document, DocumentPermission

ROLE_HIERARCHY = {
    "viewer": 1,
    "reviewer": 2,
    "owner": 3
}

async def get_permitted_document_ids(
    db: AsyncSession,
    user_id: str,
    collection_id: Optional[str] = None
) -> List[str]:
    """
    Computes the exact list of document IDs the user is authorized to access.
    Enforced BEFORE retrieval inside vector and relational queries.
    """
    # 1. Documents where user has explicit DocumentPermission
    perm_query = select(DocumentPermission.document_id).where(
        DocumentPermission.user_id == user_id
    )
    perm_res = await db.execute(perm_query)
    direct_doc_ids = set(perm_res.scalars().all())

    # 2. Documents where user is member/owner of workspace containing the collection
    ws_query = (
        select(Document.id)
        .join(Collection, Document.collection_id == Collection.id)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            or_(
                Workspace.owner_id == user_id,
                WorkspaceMember.user_id == user_id
            )
        )
    )
    if collection_id:
        ws_query = ws_query.where(Document.collection_id == collection_id)
        
    ws_res = await db.execute(ws_query)
    workspace_doc_ids = set(ws_res.scalars().all())

    permitted = list(direct_doc_ids.union(workspace_doc_ids))
    return permitted

async def check_document_access(
    db: AsyncSession,
    user_id: str,
    document_id: str,
    required_level: str = "view"
) -> Document:
    """
    Validates document access. Raises 403 Forbidden if unauthorized.
    """
    permitted_ids = await get_permitted_document_ids(db, user_id)
    if document_id not in permitted_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to view or access this document.",
        )

    res = await db.execute(select(Document).where(Document.id == document_id))
    doc = res.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc

async def check_collection_access(
    db: AsyncSession,
    user_id: str,
    collection_id: str,
    required_role: str = "viewer"
) -> Collection:
    """
    Validates collection access based on workspace role hierarchy.
    """
    res = await db.execute(
        select(Collection, Workspace, WorkspaceMember)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .outerjoin(
            WorkspaceMember,
            and_(
                WorkspaceMember.workspace_id == Workspace.id,
                WorkspaceMember.user_id == user_id
            )
        )
        .where(Collection.id == collection_id)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    collection, workspace, member = row

    if workspace.owner_id == user_id:
        return collection

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a member of this workspace.",
        )

    user_level = ROLE_HIERARCHY.get(member.role, 0)
    needed_level = ROLE_HIERARCHY.get(required_role, 1)

    if user_level < needed_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Requires role '{required_role}', but current role is '{member.role}'.",
        )

    return collection
