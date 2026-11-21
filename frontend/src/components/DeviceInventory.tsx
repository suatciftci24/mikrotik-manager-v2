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
const percent=(value:number|null)=>value==null?null:value.toLocaleString('tr-TR',{maximumFractionDigits:2})+'%';
const bytes=(value:string|null)=>value==null?null:value+' bayt';

type SubscriberRow={router:Router;account:Account};

const sessionStatus=(account:Account)=>
 account.sessions==null?'Bilinmiyor':
 account.sessions.length?'Çevrimiçi':'Çevrimdışı';

function SubscriberTable({rows,complete}:{rows:SubscriberRow[];complete:boolean}){
 const [query,setQuery]=useState('');
 const [router,setRouter]=useState('');
 const [status,setStatus]=useState('');
 const [sort,setSort]=useState<'asc'|'desc'>('asc');
 const [limit,setLimit]=useState(25);
 const [page,setPage]=useState(1);
 const [selected,setSelected]=useState<string|null>(null);
 const key=(row:SubscriberRow)=>JSON.stringify([row.router.id,row.account.username]);
 const routers=Array.from(new Map(rows.map(row=>[row.router.id,row.router.identity??row.router.id])));
 const norm=(value:string)=>value.toLocaleLowerCase('tr-TR');
 const filtered=rows.filter(({router:r,account:a})=>
  (!router||r.id===router)&&
  (!status||(status==='disabled'?a.enabled===false:sessionStatus(a)===status))&&
  norm([a.username,r.identity??r.id,a.profile??'',...(a.sessions??[]).map(x=>x.address??'')].join(' ')).includes(norm(query.trim()))
 ).sort((a,b)=>(sort==='asc'?1:-1)*a.account.username.localeCompare(b.account.username,'tr',{numeric:true}));
 const pages=Math.max(1,Math.ceil(filtered.length/limit));
 const activePage=Math.min(page,pages);
 const counts=[
  ['Görülen abone',rows.length],
  ['Çevrimiçi',rows.filter(x=>sessionStatus(x.account)==='Çevrimiçi').length],
  ['Çevrimdışı',rows.filter(x=>sessionStatus(x.account)==='Çevrimdışı').length],
  ['Devre dışı',rows.filter(x=>x.account.enabled===false).length],
 ];
 const detail=rows.find(row=>key(row)===selected);
 return <>
  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(140px,1fr))',gap:12,margin:'16px 0'}}>
   {counts.map(([label,value])=><div key={label} className="panel" style={{padding:16}}>
    <div>{label}</div><strong style={{fontSize:26}}>{value}</strong>
   </div>)}
  </div>
  {!complete&&<p>Gözlem kapsamı kısmi. Sayılar yalnızca görülen hesapları gösterir.</p>}
  <div style={{display:'flex',gap:12,flexWrap:'wrap',margin:'16px 0'}}>
   <input aria-label="Abone ara" placeholder="Abone, IP veya profil ara..." value={query}
    onChange={e=>{setQuery(e.target.value);setPage(1);}} style={{flex:1,minWidth:220,padding:10}}/>
   <select aria-label="Router filtresi" value={router} onChange={e=>{setRouter(e.target.value);setPage(1);}}>
    <option value="">Tüm routerlar</option>
    {routers.map(([id,name])=><option key={id} value={id}>{name}</option>)}
   </select>
   <select aria-label="Durum filtresi" value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}>
    <option value="">Tüm durumlar</option>
    <option>Çevrimiçi</option><option>Çevrimdışı</option>
    <option>Bilinmiyor</option><option value="disabled">Devre dışı</option>
   </select>
  </div>
  <div style={{overflowX:'auto'}}>
   <table style={{width:'100%',borderCollapse:'collapse',textAlign:'left'}}>
    <thead><tr>
     <th><button className="button-secondary" onClick={()=>{setSort(sort==='asc'?'desc':'asc');setPage(1);}}>Abone {sort==='asc'?'↑':'↓'}</button></th>
     {['Router','Profil','IP adresi','Bağlantı','Hesap','Bitiş tarihi','İşlem'].map(h=><th key={h} style={{padding:12}}>{h}</th>)}
    </tr></thead>
    <tbody>
     {filtered.slice((activePage-1)*limit,activePage*limit).map(row=>{
      const a=row.account;
      return <tr key={key(row)} style={{borderTop:'1px solid #64748b45'}}>
       {[a.username,row.router.identity??row.router.id,a.profile??'—',
        a.sessions?.map(x=>x.address).filter(Boolean).join(', ')||'—',
        sessionStatus(a),a.enabled==null?'Bilinmiyor':a.enabled?'Etkin':'Devre dışı',
        a.expires_on??'—'].map((value,i)=><td key={i} style={{padding:12}}>{value}</td>)}
       <td><button className="button-secondary" onClick={()=>setSelected(key(row))}>Detay</button></td>
      </tr>;
     })}
     {!filtered.length&&<tr><td colSpan={8} style={{padding:20}}>Eşleşen güncel abone yok.</td></tr>}
    </tbody>
   </table>
  </div>
  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:12,flexWrap:'wrap',marginTop:16}}>
   <span>{filtered.length} abone</span>
   <select aria-label="Sayfa başına abone" value={limit} onChange={e=>{setLimit(Number(e.target.value));setPage(1);}}>
    {[25,50,100].map(n=><option key={n} value={n}>{n} / sayfa</option>)}
   </select>
   <div style={{display:'flex',alignItems:'center',gap:12}}>
    <button className="button-secondary" disabled={activePage<=1} onClick={()=>setPage(activePage-1)}>Önceki</button>
    <span>{activePage} / {pages}</span>
    <button className="button-secondary" disabled={activePage>=pages} onClick={()=>setPage(activePage+1)}>Sonraki</button>
   </div>
  </div>
  {detail&&<aside className="panel" aria-label="Abone detayları" style={{marginTop:16,padding:20}}>
   <div className="page-heading-row"><h2>{detail.account.username}</h2>
    <button className="button-secondary" onClick={()=>setSelected(null)}>Kapat</button></div>
   <Facts items={[
    ['Router',detail.router.identity??detail.router.id],
    ['Profil',detail.account.profile],
    ['Bağlantı',sessionStatus(detail.account)],
    ['Hesap durumu',detail.account.enabled==null?'Bilinmiyor':detail.account.enabled?'Etkin':'Devre dışı'],
    ['Abonelik bitişi',detail.account.expires_on],
    ['Gözlenen aktif oturum',detail.account.sessions?.length??'Bilinmiyor'],
   ]}/>
   {detail.account.sessions?.map((session,i)=><Facts key={i} items={[
    ['Oturum IP adresi',session.address],['Bağlantı süresi',session.uptime]
   ]}/>)}
  </aside>}
 </>;
}

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
  {view==='subscribers'&&rows.length>0&&
   <SubscriberTable complete={complete} rows={rows.flatMap(router=>
    current(router)?(router.accounts??[]).map(account=>({router,account})):[])}/>}
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
   {view==='subscribers'&&(!current(row)||row.accounts===null)&&
    <p>Güncel PPPoE hesabı ve oturum bilgisi yok.</p>}
   {view==='subscribers'&&current(row)&&!!row.unmatched_sessions?.length&&<details>
    <summary>Yerel hesapla eşleşmeyen oturumlar</summary>
    {row.unmatched_sessions.map((session,i)=><Facts key={i} items={[
     ['Kullanıcı adı',session.username],
     ['Oturum IP adresi',session.address],
     ['Bağlantı süresi',session.uptime],
    ]}/>)}
   </details>}
  </details>)}
 </section>;
}
