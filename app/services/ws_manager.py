import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        self._connections.get(user_id, set()).discard(ws)
        if not self._connections.get(user_id):
            self._connections.pop(user_id, None)

    def is_online(self, user_id: str) -> bool:
        return user_id in self._connections and bool(self._connections[user_id])

    async def send_to_user(self, user_id: str, event: dict[str, Any]):
        for ws in self._connections.get(user_id, set()).copy():
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(user_id, ws)

    async def broadcast_to_conversation(
        self, member_ids: list[str], event: dict[str, Any], exclude: str | None = None
    ):
        for uid in member_ids:
            if uid == exclude:
                continue
            await self.send_to_user(uid, event)


manager = ConnectionManager()
