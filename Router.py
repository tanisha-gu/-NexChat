import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.services.message_service import MessageService
from app.schemas.schemas import MessageCreate
from app.websocket.manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    token: str = Query(...),
):
    # Authenticate via token query param (WS can't send headers)
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_id, room_id)

    # Notify room that user is online
    await manager.broadcast_to_room(room_id, "user_online", {"user_id": user_id})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "payload": {"detail": "Invalid JSON"}})
                )
                continue

            event_type = event.get("type")
            payload = event.get("payload", {})

            # ── Handle incoming events ──────────────────────
            if event_type == "message:send":
                async with AsyncSessionLocal() as db:
                    try:
                        msg_data = MessageCreate(**payload)
                        message = await MessageService.send(db, room_id, user_id, msg_data)
                        await db.commit()
                        serialized = MessageService._serialize(message)
                        await manager.broadcast_to_room(room_id, "message:new", serialized)
                    except Exception as e:
                        await db.rollback()
                        await websocket.send_text(
                            json.dumps({"type": "error", "payload": {"detail": str(e)}})
                        )

            elif event_type == "message:delete":
                msg_id = payload.get("message_id")
                if msg_id:
                    async with AsyncSessionLocal() as db:
                        try:
                            msg = await MessageService.delete(db, msg_id, user_id)
                            await db.commit()
                            await manager.broadcast_to_room(
                                room_id,
                                "message:deleted",
                                {"message_id": msg_id, "room_id": room_id},
                            )
                        except Exception as e:
                            await db.rollback()
                            await websocket.send_text(
                                json.dumps({"type": "error", "payload": {"detail": str(e)}})
                            )

            elif event_type == "typing:start":
                await manager.broadcast_to_room(
                    room_id,
                    "typing:start",
                    {"user_id": user_id, "room_id": room_id},
                )

            elif event_type == "typing:stop":
                await manager.broadcast_to_room(
                    room_id,
                    "typing:stop",
                    {"user_id": user_id, "room_id": room_id},
                )

            elif event_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "payload": {}}))

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, room_id)
        await manager.broadcast_to_room(room_id, "user_offline", {"user_id": user_id})
        logger.info(f"User {user_id} disconnected from room {room_id}")
