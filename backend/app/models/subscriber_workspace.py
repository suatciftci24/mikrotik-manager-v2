"""Synthetic subscribers linked by FK to persistent synthetic routers only."""
from sqlalchemy import String,Integer,JSON,ForeignKey,UniqueConstraint,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.models.router_workspace import RouterWorkspaceRecord

class SyntheticSubscriber(Base):
    __tablename__='subscribers'
    __table_args__=(UniqueConstraint('username_key'),CheckConstraint("access_type IN ('PPPOE','HOTSPOT')"),CheckConstraint("source IN ('LOCAL','RADIUS')"),{'schema':'v2_subscriber_workspace'})
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    router_id:Mapped[str]=mapped_column(ForeignKey('v2_router_workspace.records.id',ondelete='RESTRICT'))
    username_key:Mapped[str]=mapped_column(String(96))
    access_type:Mapped[str]=mapped_column(String(16))
    source:Mapped[str]=mapped_column(String(16))
    revision:Mapped[int]=mapped_column(Integer)
    fields:Mapped[dict]=mapped_column(JSON)

class SyntheticSubscriberEvent(Base):
    __tablename__='events'
    __table_args__={'schema':'v2_subscriber_workspace'}
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    subscriber_id:Mapped[str]=mapped_column(String(64),index=True)
    actor_id:Mapped[str]=mapped_column(String(80))
    occurred_at:Mapped[str]=mapped_column(String(40))
    revision:Mapped[int]=mapped_column(Integer)
    operation:Mapped[str]=mapped_column(String(20))
    changes:Mapped[dict]=mapped_column(JSON)
