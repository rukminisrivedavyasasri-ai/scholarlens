from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.audit import AuditLog

class AuditService:
    @classmethod
    def log(
        cls,
        db: Session,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        payload = details or {}
        if resource_type:
            payload["resource_type"] = resource_type
        entry = AuditLog(
            user_id=user_id,
            action_type=action,
            resource_id=resource_id,
            details=payload,
            ip_address=ip_address
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

async def log_audit_event(
    db: AsyncSession,
    action_type: str,
    user_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """
    Creates an immutable audit log entry for compliance and security tracing.
    """
    entry = AuditLog(
        user_id=user_id,
        action_type=action_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
