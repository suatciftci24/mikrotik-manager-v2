import {SyntheticManagementReport} from './ManagementReport';
import { useEffect } from 'react';
import { AlarmCenter } from '../components/AlarmCenter';
import { AlarmEvents } from '../components/AlarmEvents';
import { api, type Router } from '../lib/api';
import { buildConnectionAlarms } from '../lib/connectionAlarms';
import { useResource } from '../lib/useResource';
import { PageHeading } from '../components/PageHeading';
import { ResourceState } from '../components/Resource';

async function loadAlarms(path: string, init?: RequestInit) {
  const response = await api<{items: Router[]}>(path, init);
  return buildConnectionAlarms(response.items);
}
export function Operations({onRouter}: {onRouter: (id: string) => void}) {
  const params=new URLSearchParams(typeof window==='undefined'?'':window.location.hash.slice(1));
  const showEventHistory=params.get('view')!=='DAILY_REPORT'&&['router','kind','status','period','from','to'].some(key=>params.has(key));
  const {data, loading, error, retry} = useResource('/routers', loadAlarms);

  useEffect(() => {
    const scrollToAlarm = () => {
      const params = new URLSearchParams(window.location.hash.slice(1));
      if (params.get('module') === 'operations' && params.get('section') === 'alarms') {
        document.getElementById('central-alarm-section')?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    };
    scrollToAlarm();
    window.addEventListener('hashchange', scrollToAlarm);
    return () => window.removeEventListener('hashchange', scrollToAlarm);
  }, []);

  return <div className="screen-stack router-report">
    <SyntheticManagementReport onBack={()=>{window.location.hash='module=dashboard';}} center="operations"/>
    <details className="panel center-disclosure" open={params.get('section')==='alarms'||params.has('alarm_id')||params.has('alarm_status')||params.has('alarm_state')||params.has('severity')}><summary>Alarm Merkezi ve operatör onayları</summary>
    <PageHeading title="Alarm Merkezi" eyebrow="SENTETİK OLAYLAR" description="Alarmlar, operatör onayları ve kayıtlı olay geçmişi." actions={<button className="button-secondary" onClick={retry} disabled={loading}>Yenile</button>}/>
    <div id="central-alarm-section"><AlarmCenter/></div></details>
    <details className="panel center-disclosure"><summary>Veri kapsamı ve sınırlamalar</summary><div className="panel-title"><h2>Kaynak kapsamı</h2><span className="demo-chip">SENTETİK</span></div><p className="daily-description">V2 kaydedilmiş sentetik envanter ve hazırlanmışsa demo olay kayıtlarını gösterir. Çevrimiçi/çevrimdışı envanter durumu internet erişimini doğrulamaz. Yönetim adresi WAN adresi değildir. Yenileme yeni ölçüm veya alarm geçmişi oluşturmaz.</p></details>
    <ResourceState loading={loading} error={error} retry={retry}/>
    {data&&!loading&&!error&&<>
      <details className="panel center-disclosure" open={showEventHistory}><summary>İnternet / WAN olay geçmişi</summary><AlarmEvents routers={data.rows.map(row=>({id:row.id,name:row.name}) as Router)}/></details>
    </>}
  </div>;
}
