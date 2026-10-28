import { AlarmCenter } from '../components/AlarmCenter';
import { AlarmEvents } from '../components/AlarmEvents';
import { api, type Router } from '../lib/api';
import { buildConnectionAlarms } from '../lib/connectionAlarms';
import { useResource } from '../lib/useResource';
import { PageHeading } from '../components/PageHeading';
import { ResourceState, dateTime } from '../components/Resource';
import { StatusBadge } from '../components/Status';

async function loadAlarms(path: string, init?: RequestInit) {
  const response = await api<{items: Router[]}>(path, init);
  return buildConnectionAlarms(response.items);
}
export function Operations({onRouter}: {onRouter: (id: string) => void}) {
  const {data, loading, error, retry} = useResource('/routers', loadAlarms);
  return <div className="screen-stack router-report">
    <PageHeading title="Alarm ve Operasyon Merkezi" eyebrow="İNTERNET VE WAN" description="İnternet kesintisi ve WAN değişikliği alarm kapsamı" actions={<button className="button-secondary" onClick={retry} disabled={loading}>Yenile</button>}/>
    <AlarmCenter/>
    <section className="panel"><div className="panel-title"><h2>Kaynak kapsamı</h2><span className="demo-chip">SENTETİK</span></div><p className="daily-description">V2 kaydedilmiş sentetik envanter ve hazırlanmışsa demo olay kayıtlarını gösterir. Çevrimiçi/çevrimdışı envanter durumu internet erişimini doğrulamaz. Yönetim adresi WAN adresi değildir. Yenileme yeni ölçüm veya alarm geçmişi oluşturmaz.</p></section>
    <ResourceState loading={loading} error={error} retry={retry}/>
    {data&&!loading&&!error&&<>
      <AlarmEvents routers={data.rows.map(row=>({id:row.id,name:row.name}) as Router)}/>
      <section className="panel router-inventory"><div className="panel-title"><h2>Router bazında veri kapsamı</h2></div><p className="expiry-context">Kaynak zamanı Türkiye saatinde (Europe/Istanbul). Son envanter zamanı canlı internet kontrol zamanı değildir. Router adından detayına geçebilirsiniz.</p>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Router alarm kapsamı tablosu"><table className="data-table connection-alarm-table"><thead><tr><th>ROUTER · SENTETİK</th><th>ENVANTER DURUMU</th><th>İNTERNET</th><th>WAN / DEĞİŞİKLİK</th><th>ENVANTER KAYNAK ZAMANI</th></tr></thead><tbody>{data.rows.map(row=><tr key={row.id}><td><span className="table-main"><strong><button className="record-link" onClick={()=>onRouter(row.id)} aria-label={`${row.name} router detayını aç`}>{row.name}</button></strong><small>{row.site}</small></span></td><td><StatusBadge status={row.inventory_status}/></td><td>Veri yok</td><td>Veri yok</td><td>{row.source_time?dateTime(row.source_time):'Veri yok'}</td></tr>)}</tbody></table></div>
        {data.rows.length===0&&<p className="table-empty">Router envanteri boş. İnternet ve WAN için veri yok.</p>}
      </section>

    </>}
  </div>;
}
