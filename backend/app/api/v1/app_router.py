from fastapi import APIRouter
from app.api.v1 import auth, dashboard, modules, routers, subscribers, router_events, mikajani, reports, alarms, users, system, router_registry, router_workspace

api_router = APIRouter()
for feature in (auth.router, dashboard.router, routers.router, subscribers.router, modules.router, router_events.router, mikajani.router, reports.router, alarms.router, users.router, system.router, router_registry.router, router_workspace.router):
    api_router.include_router(feature)
