from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamped, UUIDPrimaryKey


class Router(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = 'routers'
    __table_args__ = (Index('ix_routers_status_name', 'status', 'name'),)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    management_address: Mapped[str] = mapped_column(String(64), nullable=False)
    site: Mapped[str] = mapped_column(String(120), default='', nullable=False)
    model: Mapped[str] = mapped_column(String(80), default='Unspecified', nullable=False)
    routeros_version: Mapped[str] = mapped_column(String(40), default='', nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='UNKNOWN', nullable=False)
    cpu_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
