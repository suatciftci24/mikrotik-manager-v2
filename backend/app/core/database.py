"""V2 PostgreSQL engine declaration. No connection or schema creation on import."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

settings.validate()
engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True, pool_size=5, max_overflow=5, connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=5000 -c lock_timeout=3000'})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
