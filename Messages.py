from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import PaginatedMessages
from app.services.message_service import MessageService
from app.core.security import get_current_user_id

router = APIRouter(prefix="/rooms", tags=["Messages"])


@router.get("/{room_id}/messages")
async def get_messages(
    room_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await MessageService.get_room_messages(db, room_id, user_id, page, page_size)


@router.delete("/{room_id}/messages/{message_id}")
async def delete_message(
    room_id: int,
    message_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await MessageService.delete(db, message_id, user_id)
    return {"ok": True}
