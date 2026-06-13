from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import RoomCreate, DirectRoomCreate, RoomMemberOut
from app.services.room_service import RoomService
from app.core.security import get_current_user_id

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.get("/")
async def list_rooms(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await RoomService.get_user_rooms(db, user_id)


@router.post("/direct", status_code=201)
async def create_direct_room(
    data: DirectRoomCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    room = await RoomService.create_direct(db, user_id, data.target_user_id)
    rooms = await RoomService.get_user_rooms(db, user_id)
    return next((r for r in rooms if r["id"] == room.id), {"id": room.id})


@router.post("/group", status_code=201)
async def create_group(
    data: RoomCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    room = await RoomService.create_group(db, user_id, data)
    rooms = await RoomService.get_user_rooms(db, user_id)
    return next((r for r in rooms if r["id"] == room.id), {"id": room.id})


@router.get("/{room_id}/members", response_model=list[RoomMemberOut])
async def get_room_members(
    room_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await RoomService.get_room_members(db, room_id, user_id)


@router.post("/{room_id}/read")
async def mark_as_read(
    room_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await RoomService.mark_read(db, room_id, user_id)
    return {"ok": True}
