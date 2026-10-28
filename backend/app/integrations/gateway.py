"""Authorization before dispatch. All external IO and writes are unconditionally disabled."""
from datetime import datetime,timedelta,timezone
from fastapi import HTTPException
from app.core.authorization import require_router
from app.integrations.contracts import Batch,ExternalConfiguration,SourceState,freshness
from app.integrations.synthetic import SyntheticProvider
from app.services.demo_subscriptions import DemoStorageUnavailable


def readiness():
    config=ExternalConfiguration()
    return dict(mode='DEMO / SYNTHETIC',routeros='DISCONNECTED',radius='DISCONNECTED',v1='ISOLATED',external_writes=config.external_writes,
                polling=False,secret_resolution=False,contract_version=1,read_only=True,is_demo=True,
                note='Yalnız mevcut sentetik sağlayıcı. Gerçek istemci, secret resolver, polling veya geçiş başlatılmadı.')


def provider_for(name='SYNTHETIC'):
    if name!='SYNTHETIC':raise HTTPException(403,'Harici sağlayıcı devre dışı')
    return SyntheticProvider()


def read_router(user,router_id,*,provider_name='SYNTHETIC',page=1,page_size=25):
    require_router(user,router_id,'can_view_reports')
    if not 1<=page<=1000000 or not 1<=page_size<=50:raise HTTPException(422,'Geçerli sayfa gerekli')
    provider=provider_for(provider_name)
    try:
        value=provider.read(router_id)
        batch=Batch.model_validate(value.model_dump(mode='json') if isinstance(value,Batch) else value)
        if batch.router_id!=router_id:raise ValueError('Provider scope mismatch')
        now=datetime.now(timezone.utc)
        rows=[{**row.model_dump(mode='json'),'freshness':freshness(row,now,timedelta(minutes=5)).value} for row in batch.records]
        return dict(router_id=router_id,state=SourceState.AVAILABLE,cursor=batch.cursor,total=len(rows),page=page,page_size=page_size,items=rows[(page-1)*page_size:page*page_size],is_demo=True)
    except TimeoutError:state=SourceState.TIMEOUT
    except PermissionError:state=SourceState.ACCESS_DENIED
    except Exception:state=SourceState.ERROR
    # Sanitized per-router envelope; never turn a source failure into router OFFLINE.
    return dict(router_id=router_id,state=state,cursor=None,total=None,page=page,page_size=page_size,items=[],is_demo=True,error='Sağlayıcı gözlemi alınamadı; cihaz durumu çıkarılmadı.')


def external_write(*_args,**_kwargs):raise HTTPException(403,'Harici sistem yazması devre dışı')
