from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import UserRegister, UserLogin, TokenOut, UserOut, UserUpdate
from app.services.user_service import UserService
from app.core.security import get_current_user_id

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await UserService.register(db, data)
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user, token = await UserService.authenticate(db, data.username, data.password)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await UserService.get_by_id(db, user_id)
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_profile(
    data: UserUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await UserService.update_profile(db, user_id, data)
    return UserOut.model_validate(user)
