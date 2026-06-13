from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.models import Message, RoomMember
from app.schemas.schemas import MessageCreate


class MessageService:

    @staticmethod
    async def send(db: AsyncSession, room_id: int, sender_id: int, data: MessageCreate) -> Message:
        # Verify sender is a room member
        result = await db.execute(
            select(RoomMember).where(
                and_(RoomMember.room_id == room_id, RoomMember.user_id == sender_id)
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member of this room")

        message = Message(
            room_id=room_id,
            sender_id=sender_id,
            content=data.content,
            reply_to_id=data.reply_to_id,
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)

        # Eagerly load sender for serialization
        result = await db.execute(
            select(Message)
            .where(Message.id == message.id)
            .options(selectinload(Message.sender))
        )
        return result.scalar_one()

    @staticmethod
    async def get_room_messages(
        db: AsyncSession,
        room_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        # Verify membership
        result = await db.execute(
            select(RoomMember).where(
                and_(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member of this room")

        total_result = await db.execute(
            select(func.count()).where(
                and_(Message.room_id == room_id, Message.is_deleted == False)
            )
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        msgs_result = await db.execute(
            select(Message)
            .where(and_(Message.room_id == room_id, Message.is_deleted == False))
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .options(selectinload(Message.sender))
        )
        messages = list(reversed(msgs_result.scalars().all()))

        return {
            "messages": [MessageService._serialize(m) for m in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": (offset + page_size) < total,
        }

    @staticmethod
    async def delete(db: AsyncSession, message_id: int, user_id: int) -> Message:
        result = await db.execute(
            select(Message)
            .where(Message.id == message_id)
            .options(selectinload(Message.sender))
        )
        msg = result.scalar_one_or_none()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if msg.sender_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot delete another user's message")
        msg.is_deleted = True
        msg.content = "This message was deleted"
        await db.flush()
        return msg

    @staticmethod
    def _serialize(msg: Message) -> dict:
        return {
            "id": msg.id,
            "room_id": msg.room_id,
            "sender_id": msg.sender_id,
            "sender_username": msg.sender.username,
            "sender_display_name": msg.sender.display_name,
            "sender_avatar_color": msg.sender.avatar_color,
            "content": msg.content,
            "status": msg.status.value,
            "reply_to_id": msg.reply_to_id,
            "is_deleted": msg.is_deleted,
            "created_at": msg.created_at,
        }
