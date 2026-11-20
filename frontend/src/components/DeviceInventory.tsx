import {useEffect,useState} from 'react';
import {useResource} from '../lib/useResource';
import {dateTime,Facts,ResourceState} from './Resource';

type Session={address:string|null;uptime:string|null};
type Account={username:string;profile:string|null;enabled:boolean|null;expires_on:string|null;sessions:Session[]|null};
type Router={
 id:string;identity:string|null;model:string|null;routeros_version:string|null;connection:'ONLINE'|'OFFLINE'|'UNKNOWN';
 freshness:'RECENT'|'STALE';observed_at:string;last_success_at:string|null;error:string|null;
 cpu_percent:number|null;memory_percent:number|null;uptime:string|null;wan_interface:string|null;
 wan_status:'UP'|'DOWN'|'UNKNOWN';rx_bytes:string|null;tx_bytes:string|null;
 accounts:Account[]|null;accounts_complete:boolean;unmatched_sessions:(Session&{username:string})[]|null;
};
type Inventory={source:'ROUTEROS_READ_ONLY';is_demo:false;read_only:true;authorization_expires_at?:string;routers:Router[]};
const connection={ONLINE:'Çevrimiçi',OFFLINE:'Çevrimdışı',UNKNOWN:'Bilinmiyor'} as const;
const wan={UP:'Arayüz çalışıyor',DOWN:'Arayüz çalışmıyor',UNKNOWN:'Bilinmiyor'} as const;
const errors:Record<string,string>={TIMEOUT:'Zaman aşımı',UNREACHABLE:'Hedefe ulaşılamadı',AUTHORIZATION:'Okuma yetkisi reddedildi',TLS:'TLS doğrulaması başarısız',INVALID_DATA:'Gözlem doğrulanamadı'};
const percent=(value:number|null)=>value==null?null:value+'%';
const bytes=(value:string|null)=>value==null?null:value+' bayt';

export function DeviceInventory({view}:{view:'routers'|'subscribers'|'summary'}){
 const resource=useResource<Inventory>('/device-inventory');
 const [now,setNow]=useState(Date.now);
 useEffect(()=>{
  const timer=window.setInterval(()=>{setNow(Date.now());if(!document.hidden)resource.retry();},15000);
  const resume=()=>{if(!document.hidden){setNow(Date.now());resource.retry();}};
  document.addEventListener('visibilitychange',resume);
  return()=>{window.clearInterval(timer);document.removeEventListener('visibilitychange',resume);};
 },[resource.retry]);
 const payload=resource.data;
 const expiry=payload?.authorization_expires_at;
 useEffect(()=>{
  if(expiry===undefined)return;
  const remaining=Date.parse(expiry)-Date.now();
  if(!Number.isFinite(remaining)||remaining<=0)return;
  const timer=window.setTimeout(()=>setNow(Date.now()),remaining);
  return()=>window.clearTimeout(timer);
 },[expiry]);
 const error=resource.error||(payload&&(payload.source!=='ROUTEROS_READ_ONLY'||payload.is_demo!==false||payload.read_only!==true||!Array.isArray(payload.routers))?'RouterOS veri kaynağı doğrulanamadı.':undefined);
 const authorized=expiry===undefined||Date.parse(expiry)>Math.max(now,Date.now());
 const rows=authorized&&!error&&!resource.loading?payload?.routers??[]:[];
 const recent=(row:Router)=>{
  const stamp=Date.parse(row.observed_at), age=Math.max(now,Date.now())-stamp;
  return row.freshness==='RECENT'&&Number.isFinite(stamp)&&age>=0&&age<300000;
 };
 const current=(row:Router)=>recent(row)&&row.connection==='ONLINE';
 const accounts=rows.flatMap(row=>current(row)?row.accounts??[]:[]);
 const observedSessions=accounts.reduce((n,row)=>n+(row.sessions?.length??0),0)+
  rows.reduce((n,row)=>n+(current(row)?row.unmatched_sessions?.length??0:0),0);
 const sessionCoverage=rows.every(row=>current(row)&&row.unmatched_sessions!==null&&row.accounts?.every(account=>account.sessions!==null));
 const complete=rows.every(row=>current(row)&&row.accounts!==null&&row.accounts_complete);
 return <section className="panel registry-detail" aria-label="RouterOS salt okunur gözlemler">
  <div className="page-heading-row"><h2>Gerçek cihaz · RouterOS · Salt okunur</h2><button className="button-secondary" onClick={resource.retry}>Gözlemleri yenile</button></div>
  <ResourceState {...resource} error={error}/>
  {!error&&!resource.loading&&!rows.length&&<p>RouterOS gözlem kaynağında veri yok.</p>}
  {view==='summary'&&rows.length>0&&<>
   <Facts items={[
    ['Router',rows.length],['Son gözlem çevrimiçi',rows.filter(current).length],
    ['Son gözlem çevrimdışı',rows.filter(row=>recent(row)&&row.connection==='OFFLINE').length],
    ['Güncel gözlemde görülen PPPoE hesapları',accounts.length||(!complete?'Bilinmiyor':0)],
    ['Gözlenen etkin hesaplar',accounts.length||complete?accounts.filter(row=>row.enabled===true).length:'Bilinmiyor'],
    ['Gözlenen aktif PPPoE oturumları',observedSessions||sessionCoverage?observedSessions:'Bilinmiyor'],
   ]}/>
   <p>{complete?'Görülen yerel PPPoE hesabı kapsamı':'PPPoE kapsamı eksik veya bilinmiyor'} · Son aktarım {dateTime(rows.map(row=>row.observed_at).sort((a,b)=>Date.parse(b)-Date.parse(a))[0])}</p>
  </>}
  {view!=='summary'&&rows.map(row=><details key={row.id} className="technical-info">
   <summary>{row.identity??row.id} · {connection[recent(row)?row.connection:'UNKNOWN']}</summary>
   <Facts items={[
    ['Router kimliği',row.identity],['Model',row.model],['RouterOS',row.routeros_version],
    ['Gözlem',dateTime(row.observed_at)],['Veri güncelliği',recent(row)?'Son 5 dakika':'Eski'],
    ['Son başarılı bağlantı',dateTime(row.last_success_at)],['Son gözlem hatası',row.error?errors[row.error]:null],
    ...(view==='routers'?[
     ['CPU',current(row)?percent(row.cpu_percent):null],['RAM',current(row)?percent(row.memory_percent):null],
     ['Çalışma süresi',current(row)?row.uptime:null],['WAN arayüzü',current(row)?row.wan_interface:null],
     ['WAN bağlantısı',current(row)?wan[row.wan_status]:'Bilinmiyor'],
     ['WAN alınan sayaç',current(row)?bytes(row.rx_bytes):null],['WAN gönderilen sayaç',current(row)?bytes(row.tx_bytes):null],
    ] as [string,string|null][]:[]),
   ]}/>
   {view==='subscribers'&&(!current(row)||row.accounts===null?<p>Güncel PPPoE hesabı ve oturum bilgisi yok.</p>:<>
    {!row.accounts_complete&&<p>Görülen yerel PPPoE hesapları · kapsam kısmi.</p>}
    {!row.accounts.length&&<p>Bu gözlemde PPPoE hesabı görülmedi.</p>}
    {!!row.unmatched_sessions?.length&&<details>
     <summary>Yerel hesapla eşleşmeyen oturumlar</summary>
     {row.unmatched_sessions.map((session,i)=><Facts key={i} items={[
      ['Kullanıcı adı',session.username],['Oturum IP adresi',session.address],['Bağlantı süresi',session.uptime],
     ]}/>)}
    </details>}
    {row.accounts.map(account=><details key={account.username}>
     <summary>{account.username}</summary>
     <Facts items={[
      ['Profil',account.profile],['Hesap durumu',account.enabled===null?'Bilinmiyor':account.enabled?'Etkin':'Devre dışı'],
      ['Abonelik bitişi',account.expires_on],['Gözlenen aktif oturum',account.sessions?.length??'Bilinmiyor'],
     ]}/>
     {account.sessions?.map((session,i)=><Facts key={i} items={[[ 'Oturum IP adresi',session.address],['Bağlantı süresi',session.uptime]]}/>)}
    </details>)}
   </>)}
  </details>)}
 </section>;
}
