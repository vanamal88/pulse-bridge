from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, ApiKey
from app.security import hash_api_key, new_api_key

async def get_or_create_user(db: AsyncSession, tg_user_id: int, first_name=None, username=None) -> User:
    user = await db.scalar(select(User).where(User.tg_user_id == tg_user_id))
    if user:
        user.first_name, user.username = first_name, username
        return user
    user = User(tg_user_id=tg_user_id, first_name=first_name, username=username)
    db.add(user)
    await db.flush()
    return user

async def issue_key_if_missing(db: AsyncSession, user: User) -> str | None:
    active = await db.scalar(select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None)))
    if active:
        return None
    raw = new_api_key()
    db.add(ApiKey(user_id=user.id, key_hash=hash_api_key(raw)))
    await db.flush()
    return raw

async def rotate_key(db: AsyncSession, user: User) -> str:
    from datetime import datetime, timezone
    keys = (await db.scalars(select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None)))).all()
    now = datetime.now(timezone.utc)
    for key in keys:
        key.revoked_at = now
    raw = new_api_key()
    db.add(ApiKey(user_id=user.id, key_hash=hash_api_key(raw)))
    await db.flush()
    return raw

async def user_for_key(db: AsyncSession, raw_key: str) -> User | None:
    key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw_key), ApiKey.revoked_at.is_(None)))
    if key is None:
        return None
    return await db.get(User, key.user_id)
