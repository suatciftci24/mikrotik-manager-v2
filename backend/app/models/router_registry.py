"""Isolated real-device registry; never overlays the synthetic demo inventory."""
from sqlalchemy import Index,Integer,JSON,String,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base


class RegisteredRouter(Base):
    __tablename__='v2_registered_routers'
    __table_args__=(UniqueConstraint('management_address','port'),Index('ix_v2_registered_routers_name','name'),Index('ix_v2_registered_routers_check','last_error','last_success_at'))
    id: Mapped[str]=mapped_column(String(48),primary_key=True)
    name: Mapped[str]=mapped_column(String(120))
    management_address: Mapped[str]=mapped_column(String(64))
    port: Mapped[int]=mapped_column(Integer)
    configuration: Mapped[dict]=mapped_column(JSON)
    metadata_snapshot: Mapped[dict]=mapped_column(JSON)
    credential_ref: Mapped[str]=mapped_column(String(36))
    revision: Mapped[int]=mapped_column(Integer,default=1)
    last_checked_at: Mapped[str]=mapped_column(String(40))
    last_success_at: Mapped[str]=mapped_column(String(40))
    last_error: Mapped[str|None]=mapped_column(String(200),nullable=True)


class RouterVerification(Base):
    __tablename__='v2_router_verifications'
    __table_args__=(Index('ix_v2_router_verifications_expiry','state','expires_at'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    actor_id: Mapped[str]=mapped_column(String(80),index=True)
    state: Mapped[str]=mapped_column(String(16))
    target_router_id: Mapped[str|None]=mapped_column(String(48),nullable=True)
    expected_revision: Mapped[int]=mapped_column(Integer)
    snapshot: Mapped[dict]=mapped_column(JSON)
    credential_ref: Mapped[str]=mapped_column(String(36))
    created_at: Mapped[str]=mapped_column(String(40))
    expires_at: Mapped[str]=mapped_column(String(40))
    error_code: Mapped[str|None]=mapped_column(String(200),nullable=True)
    saved_router_id: Mapped[str|None]=mapped_column(String(48),nullable=True)


class RouterRegistryAudit(Base):
    __tablename__='v2_router_registry_audit'
    __table_args__=(Index('ix_v2_router_registry_audit_time','router_id','occurred_at'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    actor_id: Mapped[str]=mapped_column(String(80))
    router_id: Mapped[str|None]=mapped_column(String(48),nullable=True,index=True)
    verification_id: Mapped[str]=mapped_column(String(36))
    action: Mapped[str]=mapped_column(String(40))
    occurred_at: Mapped[str]=mapped_column(String(40))
    details: Mapped[dict]=mapped_column(JSON)
