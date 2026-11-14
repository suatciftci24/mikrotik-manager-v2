"""Business packages for synthetic subscriptions; never RouterOS profile provisioning."""
from sqlalchemy import String,Integer,JSON,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base

class Package(Base):
    __tablename__='packages'
    __table_args__=(CheckConstraint('revision >= 1'),{'schema':'v2_subscriber_workspace'})
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    name_key:Mapped[str]=mapped_column(String(360),unique=True)
    revision:Mapped[int]=mapped_column(Integer)
    fields:Mapped[dict]=mapped_column(JSON)

class PackageEvent(Base):
    __tablename__='package_events'
    __table_args__={'schema':'v2_subscriber_workspace'}
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    package_id:Mapped[str]=mapped_column(String(64),index=True)
    actor_id:Mapped[str]=mapped_column(String(80))
    occurred_at:Mapped[str]=mapped_column(String(40))
    revision:Mapped[int]=mapped_column(Integer)
    changes:Mapped[dict]=mapped_column(JSON)
