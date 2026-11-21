from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings
from app.models import Base
_engine = None
_factory = None

def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().DATABASE_URL
        kwargs = {"pool_pre_ping": True}
        if not url.startswith("sqlite"):
            kwargs.update(pool_size=5, max_overflow=5)
        _engine = create_async_engine(url, **kwargs)
    return _engine

def get_session_factory():
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_db():
    # Development convenience only. Production schema is managed by Alembic.
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = _factory = None
