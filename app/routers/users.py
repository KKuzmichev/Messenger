from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.auth import UserResponse
from app.services import auth as auth_service


class UpdatePublicKeyRequest(BaseModel):
    public_key: str

router = APIRouter(prefix="/api/users", tags=["users"])


@router.put("/me", response_model=UserResponse)
async def update_me(body: UpdatePublicKeyRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await auth_service.update_public_key(db, user, body.public_key)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        public_key=user.public_key.hex() if user.public_key else None,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        public_key=user.public_key.hex() if user.public_key else None,
    )


@router.get("", response_model=list[UserResponse])
async def search_users(q: str = "", db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user_id)):
    users = await auth_service.search_users(db, q) if q else []
    return [
        UserResponse(id=str(u.id), username=u.username, display_name=u.display_name, public_key=u.public_key.hex() if u.public_key else None)
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user_id)):
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        public_key=user.public_key.hex() if user.public_key else None,
    )


@router.get("/{user_id}/key")
async def get_user_public_key(user_id: str, db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user_id)):
    user = await auth_service.get_user_by_id(db, user_id)
    if not user or not user.public_key:
        raise HTTPException(status_code=404, detail="Public key not found")
    return {"user_id": user_id, "public_key": user.public_key.hex()}
