from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime, timezone

from app.models.models import Room, RoomMember, Message, RoomType, User
from app.schemas.schemas import RoomCreate, MessageOut


class RoomService:

    @staticmethod
    async def create_direct(db: AsyncSession, creator_id: int, target_id: int) -> Room:
        # Check if direct room already exists between these two users
        subq1 = select(RoomMember.room_id).where(RoomMember.user_id == creator_id).scalar_subquery()
        subq2 = select(RoomMember.room_id).where(RoomMember.user_id == target_id).scalar_subquery()
        existing = await db.execute(
            select(Room).where(
                and_(
                    Room.room_type == RoomType.DIRECT,
                    Room.id.in_(subq1),
                    Room.id.in_(subq2),
                )
            )
        )
        room = existing.scalar_one_or_none()
        if room:
            return room

        room = Room(room_type=RoomType.DIRECT, created_by=creator_id)
        db.add(room)
        await db.flush()

        for uid in [creator_id, target_id]:
            db.add(RoomMember(room_id=room.id, user_id=uid, is_admin=(uid == creator_id)))
        await db.flush()
        await db.refresh(room)
        return room

    @staticmethod
    async def create_group(db: AsyncSession, creator_id: int, data: RoomCreate) -> Room:
        if not data.name:
            raise HTTPException(status_code=400, detail="Group name is required")

        room = Room(
            name=data.name,
            description=data.description,
            room_type=RoomType.GROUP,
            created_by=creator_id,
        )
        db.add(room)
        await db.flush()

        member_ids = list(set([creator_id] + data.member_ids))
        for uid in member_ids:
            db.add(RoomMember(room_id=room.id, user_id=uid, is_admin=(uid == creator_id)))
        await db.flush()
        await db.refresh(room)
        return room

    @staticmethod
    async def get_user_rooms(db: AsyncSession, user_id: int) -> list[dict]:
        result = await db.execute(
            select(Room)
            .join(RoomMember, RoomMember.room_id == Room.id)
            .where(RoomMember.user_id == user_id)
            .options(selectinload(Room.members).selectinload(RoomMember.user))
        )
        rooms = list(result.scalars().unique().all())

        enriched = []
        for room in rooms:
            # Get last message
            last_msg_result = await db.execute(
                select(Message)
                .where(and_(Message.room_id == room.id, Message.is_deleted == False))
                .order_by(Message.created_at.desc())
                .limit(1)
                .options(selectinload(Message.sender))
            )
            last_msg = last_msg_result.scalar_one_or_none()

            # Get unread count
            member = next((m for m in room.members if m.user_id == user_id), None)
            unread = 0
            if member:
                unread_result = await db.execute(
                    select(func.count()).where(
                        and_(
                            Message.room_id == room.id,
                            Message.created_at > member.last_read_at,
                            Message.sender_id != user_id,
                            Message.is_deleted == False,
                        )
                    )
                )
                unread = unread_result.scalar() or 0

            room_name = room.name
            if room.room_type == RoomType.DIRECT:
                other = next((m.user for m in room.members if m.user_id != user_id), None)
                room_name = other.display_name if other else "Unknown"

            enriched.append({
                "id": room.id,
                "name": room_name,
                "room_type": room.room_type.value,
                "description": room.description,
                "created_by": room.created_by,
                "created_at": room.created_at,
                "member_count": len(room.members),
                "last_message": RoomService._serialize_message(last_msg) if last_msg else None,
                "unread_count": unread,
            })

        enriched.sort(
            key=lambda r: r["last_message"]["created_at"] if r["last_message"] else r["created_at"],
            reverse=True,
        )
        return enriched

    @staticmethod
    def _serialize_message(msg: Optional[Message]) -> Optional[dict]:
        if not msg:
            return None
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

    @staticmethod
    async def get_room_members(db: AsyncSession, room_id: int, user_id: int) -> list[dict]:
        await RoomService._assert_member(db, room_id, user_id)
        result = await db.execute(
            select(RoomMember)
            .where(RoomMember.room_id == room_id)
            .options(selectinload(RoomMember.user))
        )
        members = list(result.scalars().all())
        return [
            {
                "user_id": m.user_id,
                "username": m.user.username,
                "display_name": m.user.display_name,
                "avatar_color": m.user.avatar_color,
                "is_online": m.user.is_online,
                "is_admin": m.is_admin,
                "joined_at": m.joined_at,
            }
            for m in members
        ]

    @staticmethod
    async def mark_read(db: AsyncSession, room_id: int, user_id: int) -> None:
        result = await db.execute(
            select(RoomMember).where(
                and_(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
            )
        )
        member = result.scalar_one_or_none()
        if member:
            member.last_read_at = datetime.now(timezone.utc)
            await db.flush()

    @staticmethod
    async def _assert_member(db: AsyncSession, room_id: int, user_id: int) -> RoomMember:
        result = await db.execute(
            select(RoomMember).where(
                and_(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=403, detail="You are not a member of this room")
        return member
