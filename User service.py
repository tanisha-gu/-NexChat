from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from fastapi import HTTPException, status

from app.models.models import User
from app.schemas.schemas import UserRegister, UserUpdate
from app.core.security import hash_password, verify_password, create_access_token


class UserService:

    @staticmethod
    async def register(db: AsyncSession, data: UserRegister) -> User:
        # Check uniqueness
        existing = await db.execute(
            select(User).where(
                or_(User.username == data.username, User.email == data.email)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already taken",
            )
        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            display_name=data.display_name,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, username: str, password: str) -> tuple[User, str]:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        token = create_access_token({"sub": str(user.id)})
        return user, token

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    async def search(db: AsyncSession, query: str, exclude_id: int) -> list[User]:
        result = await db.execute(
            select(User).where(
                or_(
                    User.username.ilike(f"%{query}%"),
                    User.display_name.ilike(f"%{query}%"),
                ),
                User.id != exclude_id,
            ).limit(20)
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_profile(db: AsyncSession, user_id: int, data: UserUpdate) -> User:
        user = await UserService.get_by_id(db, user_id)
        if data.display_name is not None:
            user.display_name = data.display_name
        if data.bio is not None:
            user.bio = data.bio
        if data.avatar_color is not None:
            user.avatar_color = data.avatar_color
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_online(db: AsyncSession, user_id: int, is_online: bool) -> None:
        from datetime import datetime, timezone
        user = await UserService.get_by_id(db, user_id)
        user.is_online = is_online
        if not is_online:
            user.last_seen = datetime.now(timezone.utc)
        await db.flush()
