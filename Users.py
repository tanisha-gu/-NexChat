from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import UserOut
from app.services.user_service import UserService
from app.core.security import get_current_user_id

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/search", response_model=list[UserOut])
async def search_users(
    q: str = Query(..., min_length=1),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return [UserOut.model_validate(u) for u in await UserService.search(db, q, user_id)]


@router.get("/{target_id}", response_model=UserOut)
async def get_user(
    target_id: int,
    _: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await UserService.get_by_id(db, target_id)
    return UserOut.model_validate(user)
