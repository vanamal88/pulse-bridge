import asyncio, json, logging
from collections import defaultdict
from fastapi import WebSocket
logger = logging.getLogger(__name__)
class ConnectionManager:
    def __init__(self):
        self._by_user: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock: self._by_user[user_id].add(ws)
    async def disconnect(self, user_id: str, ws: WebSocket):
        async with self._lock:
            self._by_user[user_id].discard(ws)
            if not self._by_user[user_id]: self._by_user.pop(user_id, None)
    async def broadcast(self, user_id: str, payload: dict):
        async with self._lock: targets = list(self._by_user.get(user_id, set()))
        dead = []
        data = json.dumps(payload, ensure_ascii=False, default=str)
        for ws in targets:
            try: await ws.send_text(data)
            except Exception: dead.append(ws)
        for ws in dead: await self.disconnect(user_id, ws)
manager = ConnectionManager()
