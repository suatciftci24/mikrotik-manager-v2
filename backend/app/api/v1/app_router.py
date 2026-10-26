from fastapi import APIRouter
from app.api.v1 import auth, dashboard, modules, routers, subscribers

api_router = APIRouter()
for feature in (auth.router, dashboard.router, routers.router, subscribers.router, modules.router):
    api_router.include_router(feature)
