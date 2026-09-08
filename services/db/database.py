from services.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    echo=False
)
