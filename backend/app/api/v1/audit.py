from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict, Any

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.audit import AuditLog
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

@router.get("", response_model=List[Dict[str, Any]])
async def get_audit_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns audit timeline of user events (registration, logins, uploads, permission changes).
    """
    query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    res = await db.execute(query)
    logs = res.scalars().all()
    return [
        {
            "id": l.id,
            "action_type": l.action_type,
            "user_id": l.user_id,
            "resource_id": l.resource_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None
        }
        for l in logs
    ]
