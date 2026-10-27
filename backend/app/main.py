from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.services import demo_subscriptions
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.app_router import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version='0.1.0', docs_url='/api/docs')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=['GET', 'POST'],
    allow_headers=['Content-Type', 'X-V2-Demo-Action'],
)
app.include_router(api_router, prefix='/api/v1')


@app.exception_handler(demo_subscriptions.DemoStorageUnavailable)
def demo_storage_unavailable(_request, _error):
    return JSONResponse(status_code=503, content={'detail': 'V2 demo veritabanına erişilemiyor. Yerel geliştirme veritabanını ve demo şema kurulumunu kontrol edin; işlem belleğe düşürülmedi.'})


@app.get('/api/health', tags=['system'])
def health():
    ping = getattr(demo_subscriptions.store, 'ping', None)
    connected = bool(ping and ping())
    return {'status': 'ok', 'environment': 'local-demo', 'database_connected': connected,
            'demo_persistence': 'local-postgresql-demo' if connected else 'process-memory',
            'device_adapters_connected': False}
