"""Separate local workspace; never imported by live registry persistence."""
from sqlalchemy import String,Integer,JSON,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base

class RouterWorkspaceRecord(Base):
    __tablename__='records'
    __table_args__=(CheckConstraint("kind IN ('DEMO_ROUTER','TRUST_PROFILE')"),{'schema':'v2_router_workspace'})
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    kind:Mapped[str]=mapped_column(String(20))
    revision:Mapped[int]=mapped_column(Integer)
    fields:Mapped[dict]=mapped_column(JSON)

class RouterWorkspaceAudit(Base):
    __tablename__='audit'
    __table_args__={'schema':'v2_router_workspace'}
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    record_id:Mapped[str]=mapped_column(String(64),index=True)
    actor_id:Mapped[str]=mapped_column(String(80))
    action:Mapped[str]=mapped_column(String(20))
    occurred_at:Mapped[str]=mapped_column(String(40))
    revision:Mapped[int]=mapped_column(Integer)
