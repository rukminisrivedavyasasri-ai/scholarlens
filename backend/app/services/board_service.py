from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from backend.app.models.board import EvidenceBoardItem
from backend.app.models.document import Document
from backend.app.services.acl_service import get_permitted_document_ids
from backend.app.services.audit_service import log_audit_event

class BoardService:
    """
    Evidence Board management service.
    Handles proposing, approving, rejecting, and undoing evidence cards with role-based access control.
    """

    @classmethod
    async def list_board_items(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        user_role: str = "viewer"
    ) -> List[Dict[str, Any]]:
        # Fetch permitted documents for this user
        permitted_doc_ids = await get_permitted_document_ids(db, user_id)
        if not permitted_doc_ids:
            return []

        stmt = select(EvidenceBoardItem).where(
            EvidenceBoardItem.workspace_id == workspace_id,
            EvidenceBoardItem.document_id.in_(permitted_doc_ids)
        ).order_by(EvidenceBoardItem.created_at.desc())
        res = await db.execute(stmt)
        items = res.scalars().all()

        results = []
        for item in items:
            doc_res = await db.execute(select(Document).where(Document.id == item.document_id))
            doc = doc_res.scalars().first()
            results.append({
                "id": item.id,
                "workspace_id": item.workspace_id,
                "document_id": item.document_id,
                "document_title": doc.title if doc else "Unknown Document",
                "title": item.title,
                "claim": item.claim,
                "citation_excerpt": item.citation_excerpt,
                "page_number": item.page_number,
                "evidence_status": item.evidence_status,
                "board_status": item.board_status,
                "reviewed_by": item.reviewed_by,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
                "created_at": item.created_at.isoformat() if item.created_at else None
            })
        return results

    @classmethod
    async def propose_item(
        cls,
        db: AsyncSession,
        workspace_id: str,
        document_id: str,
        title: str,
        claim: str,
        citation_excerpt: Optional[str],
        page_number: Optional[int],
        evidence_status: str,
        user_id: str,
        user_role: str = "viewer"
    ) -> Dict[str, Any]:
        # Check document permission
        permitted = await get_permitted_document_ids(db, user_id)
        if document_id not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot propose evidence from an unauthorized document."
            )

        item = EvidenceBoardItem(
            workspace_id=workspace_id,
            document_id=document_id,
            title=title,
            claim=claim,
            citation_excerpt=citation_excerpt,
            page_number=page_number,
            evidence_status=evidence_status,
            board_status="proposed",
            previous_status=None,
            reviewed_by=None,
            reviewed_at=None
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)

        await log_audit_event(
            db=db,
            user_id=user_id,
            action_type="PROPOSE_EVIDENCE_ITEM",
            resource_id=item.id,
            details={"title": title, "status": "proposed"}
        )

        return {
            "id": item.id,
            "workspace_id": item.workspace_id,
            "document_id": item.document_id,
            "title": item.title,
            "claim": item.claim,
            "citation_excerpt": item.citation_excerpt,
            "page_number": item.page_number,
            "evidence_status": item.evidence_status,
            "board_status": item.board_status,
            "created_at": item.created_at.isoformat()
        }

    @classmethod
    async def approve_item(
        cls,
        db: AsyncSession,
        item_id: str,
        user_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        if user_role not in ["owner", "reviewer"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Viewer role cannot approve evidence items."
            )

        res = await db.execute(select(EvidenceBoardItem).where(EvidenceBoardItem.id == item_id))
        item = res.scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="Evidence item not found.")

        permitted = await get_permitted_document_ids(db, user_id)
        if item.document_id not in permitted:
            raise HTTPException(status_code=403, detail="Forbidden: No access to underlying document.")

        item.previous_status = item.board_status
        item.board_status = "approved"
        item.reviewed_by = user_id
        item.reviewed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(item)

        await log_audit_event(
            db=db,
            user_id=user_id,
            action_type="APPROVE_EVIDENCE_ITEM",
            resource_id=item.id,
            details={"new_status": "approved", "previous_status": item.previous_status}
        )

        return {"id": item.id, "board_status": item.board_status, "previous_status": item.previous_status}

    @classmethod
    async def reject_item(
        cls,
        db: AsyncSession,
        item_id: str,
        user_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        if user_role not in ["owner", "reviewer"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Viewer role cannot reject evidence items."
            )

        res = await db.execute(select(EvidenceBoardItem).where(EvidenceBoardItem.id == item_id))
        item = res.scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="Evidence item not found.")

        permitted = await get_permitted_document_ids(db, user_id)
        if item.document_id not in permitted:
            raise HTTPException(status_code=403, detail="Forbidden: No access to underlying document.")

        item.previous_status = item.board_status
        item.board_status = "rejected"
        item.reviewed_by = user_id
        item.reviewed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(item)

        await log_audit_event(
            db=db,
            user_id=user_id,
            action_type="REJECT_EVIDENCE_ITEM",
            resource_id=item.id,
            details={"new_status": "rejected", "previous_status": item.previous_status}
        )

        return {"id": item.id, "board_status": item.board_status, "previous_status": item.previous_status}

    @classmethod
    async def undo_action(
        cls,
        db: AsyncSession,
        item_id: str,
        user_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        if user_role not in ["owner", "reviewer"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Viewer role cannot undo evidence decisions."
            )

        res = await db.execute(select(EvidenceBoardItem).where(EvidenceBoardItem.id == item_id))
        item = res.scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="Evidence item not found.")

        permitted = await get_permitted_document_ids(db, user_id)
        if item.document_id not in permitted:
            raise HTTPException(status_code=403, detail="Forbidden: No access to underlying document.")

        if not item.previous_status:
            raise HTTPException(status_code=400, detail="No previous status to undo.")

        reverted_status = item.previous_status
        item.previous_status = item.board_status
        item.board_status = reverted_status
        item.reviewed_by = user_id
        item.reviewed_at = datetime.utcnow()
        await db.commit()
        await db.refresh(item)

        await log_audit_event(
            db=db,
            user_id=user_id,
            action_type="UNDO_EVIDENCE_ITEM",
            resource_id=item.id,
            details={"reverted_to": reverted_status}
        )

        return {"id": item.id, "board_status": item.board_status, "previous_status": item.previous_status}
