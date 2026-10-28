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
        summary=dict(states=sorted({row['freshness'] for row in rows}),observed_at=max((row['observed_at'] for row in rows if row['observed_at']),default=None),no_data=sum(row['freshness']=='NO_DATA' for row in rows))
        return dict(router_id=router_id,state=SourceState.AVAILABLE,cursor=batch.cursor,summary=summary,total=len(rows),page=page,page_size=page_size,items=rows[(page-1)*page_size:page*page_size],is_demo=True)
    except TimeoutError:state=SourceState.TIMEOUT
    except PermissionError:state=SourceState.ACCESS_DENIED
    except Exception:state=SourceState.ERROR
    # Sanitized per-router envelope; never turn a source failure into router OFFLINE.
    return dict(router_id=router_id,state=state,cursor=None,total=None,page=page,page_size=page_size,items=[],is_demo=True,error='Sağlayıcı gözlemi alınamadı; cihaz durumu çıkarılmadı.')


def external_write(*_args,**_kwargs):raise HTTPException(403,'Harici sistem yazması devre dışı')


def resilience(user):
    """Read current sources independently; no hidden retry/cache or fault injection API."""
    from app.core.authorization import routers_for
    rows=[]
    for router in routers_for(user,'can_view_reports'):
        response=read_router(user,router['id'],page_size=50)
        # Summary is computed over the full authorized batch in one provider read.
        observations=response['items']
        summary=response.get('summary') or dict(states=sorted({item['freshness'] for item in observations}),observed_at=max((item['observed_at'] for item in observations if item['observed_at']),default=None),no_data=sum(item['freshness']=='NO_DATA' for item in observations))
        states=set(summary['states'])
        status='DEGRADED' if response['state']!=SourceState.AVAILABLE else 'STALE' if 'STALE' in states else 'UNKNOWN' if not states or states<={'UNKNOWN','NO_DATA'} else 'AVAILABLE'
        rows.append(dict(router_id=router['id'],status=status,source_state=response['state'],observed_at=summary['observed_at'],no_data=summary['no_data']))
    status='UNKNOWN' if not rows else 'DEGRADED' if any(row['status']=='DEGRADED' for row in rows) else 'STALE' if any(row['status']=='STALE' for row in rows) else 'UNKNOWN' if any(row['status']=='UNKNOWN' for row in rows) else 'AVAILABLE'
    return dict(status=status,checked_at=datetime.now(timezone.utc).isoformat(),items=rows,automatic_retry=False,last_success=None,is_demo=True,
                note='Mevcut sentetik gözlemler; AVAILABLE canlı bağlantı değildir. Kalıcı senkronizasyon/otomatik retry çalışmıyor; toparlanma yalnız offline önizlemede doğrulanır.')
