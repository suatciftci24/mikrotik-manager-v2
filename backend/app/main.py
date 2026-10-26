from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.app_router import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version='0.1.0', docs_url='/api/docs')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=['GET', 'POST'],
    allow_headers=['Content-Type'],
)
app.include_router(api_router, prefix='/api/v1')


@app.get('/api/health', tags=['system'])
def health():
    return {'status': 'ok', 'environment': 'local-demo', 'database_connected': False,
            'device_adapters_connected': False}
