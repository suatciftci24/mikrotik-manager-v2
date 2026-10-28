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


@app.get('/api/ready', tags=['system'])
async def ready():
    # Liveness identity only: DB health stays on /api/health, without thread-worker dependency here.
    return {'service':'mikrotik-manager-v2', 'environment':settings.environment,
            'api_version':'v1', 'database_checked':False}


# Never echo credential inputs in validation responses (including model-level errors).
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def invalid_request(_request,error):
    return JSONResponse(status_code=422,content={'detail':'İstek alanları doğrulanamadı.','errors':[{'loc':list(issue['loc']),'msg':issue['msg'],'type':issue['type']} for issue in error.errors()]})
