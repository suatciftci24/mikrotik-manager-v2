"""Fixed pilot read descriptors over the existing bounded RouterOS wire. No generic execute."""
from types import MappingProxyType
import re
from app.adapters.cebeci_api_ssl import ApiSslStop,_Wire

DETAIL_FIELDS=MappingProxyType({
 '/interface':('.id','name','type','disabled','running'),
 '/ip/route':('dst-address','gateway','active','disabled'),
 '/ppp/secret':('.id','service','disabled'),
 '/ip/hotspot/user':('.id','disabled'),
})

class RegistryReadWire(_Wire):
    def fixed_read(self,menu):
        if menu not in DETAIL_FIELDS:raise ApiSslStop('READ_SCOPE_REJECTED')
        fields=DETAIL_FIELDS[menu];self.send((menu+'/print','=.proplist='+','.join(fields)));rows=[]
        while True:
            words=self.sentence()
            if words==['!done']:return rows
            if not words or words[0]!='!re':raise ApiSslStop('READ_ONLY_RESPONSE_REJECTED')
            row={}
            for word in words[1:]:
                parts=word.split('=',2)
                if len(parts)!=3 or parts[0] or parts[1] not in fields or parts[1] in row:raise ApiSslStop('UNEXPECTED_RESPONSE_FIELD')
                value=parts[2]
                if len(value)>160 or any(ord(c)<32 for c in value) or re.search(r'password|passwd|secretref:|token=|psk=|private.key|-----begin',value,re.I):raise ApiSslStop('SENSITIVE_METADATA_REJECTED')
                row[parts[1]]=value
            if set(row)!=set(fields):raise ApiSslStop('READ_ONLY_RESPONSE_REJECTED')
            for field in ('disabled','running','active'):
                if field in row:
                    if row[field] not in ('true','false','yes','no'):raise ApiSslStop('READ_ONLY_RESPONSE_REJECTED')
                    row[field]=row[field] in ('true','yes')
            rows.append(row)
            if len(rows)>128:raise ApiSslStop('ROW_LIMIT')

def snapshot(wire,metadata,resource,password):
    rows={menu:wire.fixed_read(menu) for menu in DETAIL_FIELDS}
    if any(password in str(value) for group in rows.values() for row in group for value in row.values()):raise ApiSslStop('SENSITIVE_METADATA_REJECTED')
    try:
        cpu=int(resource['cpu-load']);total=int(resource['total-memory']);free=int(resource['free-memory'])
        if not 0<=cpu<=100 or total<=0 or not 0<=free<=total:raise ValueError()
        uptime=resource['uptime']
        if not uptime or len(uptime)>80:raise ValueError()
    except (ValueError,KeyError,TypeError):raise ApiSslStop('RESOURCE_METRICS_REJECTED') from None
    ppp=rows['/ppp/secret'];explicit=sum(r['service']=='pppoe' for r in ppp);ambiguous=sum(r['service']=='any' for r in ppp)
    from datetime import datetime,timezone
    return dict(**metadata,cpu_percent=cpu,memory_percent=round((total-free)*100/total,2),uptime=uptime,
        captured_at=datetime.now(timezone.utc).isoformat(),interfaces=rows['/interface'],
        default_routes=[r for r in rows['/ip/route'] if r['dst-address']=='0.0.0.0/0'],wan_ip=None,
        pppoe_count=None if ambiguous else explicit,pppoe_explicit_count=explicit,ppp_any_count=ambiguous,
        hotspot_count=len(rows['/ip/hotspot/user']),is_demo=False,read_only=True)
