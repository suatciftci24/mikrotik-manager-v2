"""Pure source projections. Never probe a router, read vaults, or create missing values."""
from app.schemas.router_center import RouterCenterData

SECTIONS=('overview','interfaces','wan','pppoe','hotspot','events','security')

def center(source,item,events=()):
    return RouterCenterData(item=item,source=source,is_demo=source!='REGISTERED',
        sections={key:('AVAILABLE' if key in ('overview','events','security') or source!='REGISTERED' and key in ('pppoe','hotspot') else 'PREPARING' if source=='REGISTERED' else 'UNMEASURED') for key in SECTIONS},events=list(events))

def persistent_demo(row,events=()):
    if row['kind']!='DEMO_ROUTER' or row['is_demo'] is not True:raise ValueError('Demo source mismatch')
    fields=row['fields']
    return center('PERSISTENT_DEMO',dict(id=row['id'],name=fields['name'],model=fields['model'],management_address=fields['management_address'],site=fields.get('site'),status='UNMEASURED'),events)

def registered(row,events=()):
    if row['is_demo'] is not False:raise ValueError('Registered source mismatch')
    # Only saved, verified metadata. Last probe is historical, never current ONLINE.
    return center('REGISTERED',{key:row.get(key) for key in ('id','name','identity','model','routeros_version','management_address','status','last_success_at')},
        [dict(action=e['action'],occurred_at=e['occurred_at'],actor_id=e['actor_id']) for e in events])

def static_demo(row):
    if row['is_demo'] is not True:raise ValueError('Static source mismatch')
    return center('STATIC_DEMO',dict(id=row['id'],name=row['name'],model=row.get('model'),routeros_version=row.get('routeros_version'),
        management_address=row['management_address'],site=row.get('site'),status='SYNTHETIC_SNAPSHOT',last_seen_at=row.get('last_seen'),
        cpu_percent=row.get('cpu_percent'),memory_percent=row.get('memory_percent'),uptime=row.get('uptime')))
