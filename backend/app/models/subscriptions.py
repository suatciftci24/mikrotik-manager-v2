from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum as SqlEnum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamped, UUIDPrimaryKey


class AuthoritativeSource(str, Enum):
    LOCAL = 'LOCAL'
    RADIUS = 'RADIUS'


class Customer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = 'customers'
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default='ACTIVE', nullable=False)


class SubscriptionPlan(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = 'subscription_plans'
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    download_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SubscriberAccount(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = 'subscriber_accounts'
    __table_args__ = (
        UniqueConstraint('router_id', 'username', name='uq_subscriber_router_username'),
        CheckConstraint(
            "(authoritative_source = 'LOCAL' AND local_secret_ref IS NOT NULL AND radius_identity IS NULL) OR "
            "(authoritative_source = 'RADIUS' AND radius_identity IS NOT NULL AND local_secret_ref IS NULL)",
            name='ck_subscriber_exactly_one_authority',
        ),
        Index('ix_subscriber_status_source', 'status', 'authoritative_source'),
    )
    customer_id: Mapped[UUID] = mapped_column(ForeignKey('customers.id', ondelete='RESTRICT'), nullable=False)
    router_id: Mapped[UUID] = mapped_column(ForeignKey('routers.id', ondelete='RESTRICT'), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey('subscription_plans.id', ondelete='RESTRICT'), nullable=False)
    username: Mapped[str] = mapped_column(String(96), nullable=False)
    authoritative_source: Mapped[AuthoritativeSource] = mapped_column(
        SqlEnum(AuthoritativeSource, name='subscriber_authoritative_source', native_enum=False), nullable=False,
    )
    local_secret_ref: Mapped[str | None] = mapped_column(String(180))
    radius_identity: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(24), default='ACTIVE', nullable=False)
