from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import UUIDPrimaryKey, utc_now


class SubscriberEvent(UUIDPrimaryKey, Base):
    __tablename__ = 'subscriber_events'
    subscriber_account_id: Mapped[UUID] = mapped_column(ForeignKey('subscriber_accounts.id', ondelete='RESTRICT'), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey('panel_users.id', ondelete='SET NULL'))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditLog(UUIDPrimaryKey, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey('panel_users.id', ondelete='SET NULL'), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
