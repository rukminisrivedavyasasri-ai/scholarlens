from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, WorkspaceMember, Collection
from backend.app.schemas.auth import UserRegister, UserLogin, Token, UserResponse
from backend.app.services.auth_service import hash_password, verify_password, create_access_token, get_current_user
from backend.app.services.audit_service import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token)
async def register(req: UserRegister, request: Request, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    existing = await db.execute(select(User).where(User.email == req.email.lower()))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Create user
    user = User(
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role or "researcher"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create default workspace and collection for new user
    workspace = Workspace(
        name=f"{req.full_name}'s Primary Workspace",
        owner_id=user.id
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)

    # Add owner membership
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner"
    )
    db.add(member)

    # Add default collection
    collection = Collection(
        workspace_id=workspace.id,
        name="Clinical Trial Protocols (2024)",
        description="Approved clinical trial and cognitive intervention papers."
    )
    db.add(collection)
    await db.commit()

    # Log audit event
    await log_audit_event(
        db=db,
        action_type="AUTH_REGISTER",
        user_id=user.id,
        resource_id=user.id,
        details={"email": user.email, "role": user.role},
        ip_address=request.client.host if request.client else None
    )

    access_token = create_access_token(data={"sub": user.id, "email": user.email})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.post("/login", response_model=Token)
async def login(req: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == req.email.lower()))
    user = res.scalars().first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated.")

    # Log audit event
    await log_audit_event(
        db=db,
        action_type="AUTH_LOGIN",
        user_id=user.id,
        resource_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None
    )

    access_token = create_access_token(data={"sub": user.id, "email": user.email})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
