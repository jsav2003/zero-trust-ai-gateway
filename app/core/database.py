from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

# 1. Create the asynchronous engine with optimization parameters
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,               # Set to True only for heavy SQL debugging in development
    pool_pre_ping=True,       # Automatically tests stale connections before executing queries
    pool_size=20,             # Maintain up to 20 persistent connections
    max_overflow=10           # Allow up to 10 additional temporary connections under spikes
)

# 2. Build the asynchronous session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False    # Prevents unnecessary lazy loading queries after commits
)
