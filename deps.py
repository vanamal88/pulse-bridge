import secrets, time
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.users import user_for_key

_ws_tokens: dict[str, tuple[str, float]] = {}
async def current_user(x_api_key: str | None = Header(default=None, alias="X-API-Key"), db: AsyncSession = Depends(get_db)):
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key")
    user = await user_for_key(db, x_api_key)
    if user is None:
        raise HTTPException(401, "Invalid or revoked API key")
    return user

def issue_ws_token(user_id: str, ttl: int):
    now = time.monotonic()
    for token, (_, expiry) in list(_ws_tokens.items()):
        if expiry < now: _ws_tokens.pop(token, None)
    token = secrets.token_urlsafe(32)
    _ws_tokens[token] = (user_id, now + ttl)
    return token

def consume_ws_token(token: str):
    item = _ws_tokens.pop(token, None)
    if not item or item[1] < time.monotonic(): return None
    return item[0]
