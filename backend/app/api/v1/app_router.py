from app.api.v1 import v1_inventory
from fastapi import APIRouter
from app.api.v1 import auth, dashboard, modules, routers, subscribers, router_events, mikajani, reports, alarms, users, system, router_registry, router_workspace, router_center, subscriber_center

api_router = APIRouter()
api_router.include_router(v1_inventory.router)
for feature in (auth.router, dashboard.router, routers.router, subscribers.router, modules.router, router_events.router, mikajani.router, reports.router, alarms.router, users.router, system.router, router_registry.router, router_workspace.router, router_center.router, subscriber_center.router):
    api_router.include_router(feature)

from app.api.v1 import aaa_demo
api_router.include_router(aaa_demo.router)
