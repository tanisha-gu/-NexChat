import json
import logging
from collections import defaultdict
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages all active WebSocket connections.

    Architecture:
    - _room_connections: room_id → set of (user_id, WebSocket)
    - _user_connections: user_id → set of WebSocket (a user can have multiple tabs)

    This allows broadcasting to a room, or targeting a specific user.
    """

    def __init__(self):
        self._room_connections: dict[int, set[tuple[int, WebSocket]]] = defaultdict(set)
        self._user_connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: int, room_id: int) -> None:
        await websocket.accept()
        self._room_connections[room_id].add((user_id, websocket))
        self._user_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected to room {room_id}")

    def disconnect(self, websocket: WebSocket, user_id: int, room_id: int) -> None:
        self._room_connections[room_id].discard((user_id, websocket))
        self._user_connections[user_id].discard(websocket)
        if not self._room_connections[room_id]:
            del self._room_connections[room_id]
        logger.info(f"User {user_id} disconnected from room {room_id}")

    async def broadcast_to_room(self, room_id: int, event_type: str, payload: dict) -> None:
        """Send an event to every connected socket in a room."""
        message = json.dumps({"type": event_type, "payload": payload}, default=str)
        dead = set()
        for user_id, ws in list(self._room_connections.get(room_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add((user_id, ws))

        for pair in dead:
            self._room_connections[room_id].discard(pair)

    async def send_to_user(self, user_id: int, event_type: str, payload: dict) -> None:
        """Send an event directly to a specific user (all their tabs)."""
        message = json.dumps({"type": event_type, "payload": payload}, default=str)
        dead = set()
        for ws in list(self._user_connections.get(user_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._user_connections[user_id].discard(ws)

    def is_user_online(self, user_id: int) -> bool:
        return bool(self._user_connections.get(user_id))

    def get_online_users_in_room(self, room_id: int) -> set[int]:
        return {uid for uid, _ in self._room_connections.get(room_id, set())}


# Singleton instance — shared across the entire app
manager = ConnectionManager()
