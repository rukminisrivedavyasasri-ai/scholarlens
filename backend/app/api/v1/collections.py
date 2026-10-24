from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, WorkspaceMember, Collection
from backend.app.schemas.document import (
    CollectionCreate,
    CollectionResponse,
    CollectionMemberResponse,
    CollectionMemberInvite,
    CollectionMemberUpdate
)
from backend.app.services.auth_service import get_current_user
from backend.app.services.acl_service import check_collection_access

router = APIRouter(prefix="/collections", tags=["Collections"])

@router.get("", response_model=List[CollectionResponse])
async def list_collections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all collections accessible to the current user through owned workspaces or memberships,
    annotated with the user's role on each collection (owner, reviewer, or viewer).
    """
    query = (
        select(Collection, Workspace.owner_id, WorkspaceMember.role)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .outerjoin(
            WorkspaceMember,
            and_(
                WorkspaceMember.workspace_id == Workspace.id,
                WorkspaceMember.user_id == current_user.id
            )
        )
        .where(
            or_(
                Workspace.owner_id == current_user.id,
                WorkspaceMember.user_id == current_user.id
            )
        )
        .distinct()
    )
    res = await db.execute(query)
    rows = res.all()
    results = []
    for coll, owner_id, member_role in rows:
        role = "owner" if owner_id == current_user.id else (member_role or "viewer")
        data = CollectionResponse.model_validate(coll)
        data.user_role = role
        results.append(data)
    return results

@router.post("", response_model=CollectionResponse)
async def create_collection(
    req: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find user's owned workspace
    res = await db.execute(select(Workspace).where(Workspace.owner_id == current_user.id))
    workspace = res.scalars().first()
    if not workspace:
        # Create workspace if not present
        workspace = Workspace(name=f"{current_user.full_name}'s Workspace", owner_id=current_user.id)
        db.add(workspace)
        await db.commit()
        await db.refresh(workspace)

    collection = Collection(
        workspace_id=workspace.id,
        name=req.name,
        description=req.description
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    resp = CollectionResponse.model_validate(collection)
    resp.user_role = "owner"
    return resp

@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    collection = await check_collection_access(db, current_user.id, collection_id, required_role="viewer")
    ws_res = await db.execute(select(Workspace).where(Workspace.id == collection.workspace_id))
    ws = ws_res.scalars().first()
    role = "owner"
    if ws and ws.owner_id != current_user.id:
        mem_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id,
                WorkspaceMember.user_id == current_user.id
            )
        )
        mem = mem_res.scalars().first()
        role = mem.role if mem else "viewer"
    
    resp = CollectionResponse.model_validate(collection)
    resp.user_role = role
    return resp

@router.get("/{collection_id}/members", response_model=List[CollectionMemberResponse])
async def list_collection_members(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List members belonging to the collection's workspace.
    """
    collection = await check_collection_access(db, current_user.id, collection_id, required_role="viewer")
    ws_res = await db.execute(select(Workspace).where(Workspace.id == collection.workspace_id))
    ws = ws_res.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Get owner info
    owner_res = await db.execute(select(User).where(User.id == ws.owner_id))
    owner = owner_res.scalars().first()

    members_res = await db.execute(
        select(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == ws.id)
    )
    members_data = members_res.all()

    results: List[CollectionMemberResponse] = []
    if owner:
        results.append(CollectionMemberResponse(
            id=f"owner-{owner.id}",
            workspace_id=ws.id,
            user_id=owner.id,
            email=owner.email,
            full_name=owner.full_name,
            role="owner",
            created_at=ws.created_at
        ))

    for wm, u in members_data:
        results.append(CollectionMemberResponse(
            id=wm.id,
            workspace_id=wm.workspace_id,
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=wm.role,
            created_at=wm.created_at
        ))

    return results

@router.post("/{collection_id}/members", response_model=CollectionMemberResponse)
async def invite_collection_member(
    collection_id: str,
    invite: CollectionMemberInvite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invite / add a registered user to this collection's workspace as reviewer or viewer.
    Requires workspace owner role.
    """
    collection = await check_collection_access(db, current_user.id, collection_id, required_role="viewer")
    ws_res = await db.execute(select(Workspace).where(Workspace.id == collection.workspace_id))
    ws = ws_res.scalars().first()
    if not ws or ws.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the collection workspace owner can invite or manage members."
        )

    # Find user by email
    target_res = await db.execute(select(User).where(User.email == invite.email.strip().lower()))
    target_user = target_res.scalars().first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{invite.email}' not found. They must register first."
        )

    if target_user.id == ws.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite the workspace owner."
        )

    # Check if already a member
    mem_res = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == target_user.id
        )
    )
    existing_member = mem_res.scalars().first()
    if existing_member:
        existing_member.role = invite.role
        await db.commit()
        await db.refresh(existing_member)
        return CollectionMemberResponse(
            id=existing_member.id,
            workspace_id=ws.id,
            user_id=target_user.id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=existing_member.role,
            created_at=existing_member.created_at
        )

    new_member = WorkspaceMember(
        workspace_id=ws.id,
        user_id=target_user.id,
        role=invite.role
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)

    return CollectionMemberResponse(
        id=new_member.id,
        workspace_id=ws.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=new_member.role,
        created_at=new_member.created_at
    )

@router.put("/{collection_id}/members/{user_id}", response_model=CollectionMemberResponse)
async def update_member_role(
    collection_id: str,
    user_id: str,
    update: CollectionMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    collection = await check_collection_access(db, current_user.id, collection_id, required_role="viewer")
    ws_res = await db.execute(select(Workspace).where(Workspace.id == collection.workspace_id))
    ws = ws_res.scalars().first()
    if not ws or ws.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the collection workspace owner can update member roles."
        )

    mem_res = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == user_id
        )
    )
    member = mem_res.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in workspace.")

    u_res = await db.execute(select(User).where(User.id == user_id))
    user = u_res.scalars().first()

    member.role = update.role
    await db.commit()
    await db.refresh(member)

    return CollectionMemberResponse(
        id=member.id,
        workspace_id=ws.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        created_at=member.created_at
    )

@router.delete("/{collection_id}/members/{user_id}")
async def revoke_member_access(
    collection_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    collection = await check_collection_access(db, current_user.id, collection_id, required_role="viewer")
    ws_res = await db.execute(select(Workspace).where(Workspace.id == collection.workspace_id))
    ws = ws_res.scalars().first()
    if not ws or ws.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the collection workspace owner can revoke member access."
        )

    mem_res = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == user_id
        )
    )
    member = mem_res.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in workspace.")

    await db.delete(member)
    await db.commit()

    return {"message": "Member access revoked successfully."}
