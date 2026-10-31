import type {DailySummary} from '../lib/dailySummary';
import {PppoeObservations} from './PppoeObservations';

export function DashboardPppoe({data}:{data:DailySummary}){
 return <section className="panel" aria-label="Dashboard PPPoE veri kaynağı ve tazelik">
  <h2>PPPoE veri kaynağı ve tazelik</h2>
  <p>LOCAL: {data.subscribers.local} · RADIUS: {data.subscribers.radius} · Yetkili kaynak bilinmiyor: {data.subscribers.unknown_source}. Bunlar sentetik hesapların yetkili kaynaklarıdır; ölçüm veya oturum sayısı değildir.</p>
  <p>Veri tazeliği: <strong>Bilinmiyor</strong> · Son ölçüm: <strong>Bilinmiyor</strong>. Güvenilir PPPoE ölçümü bulunmuyor. Özet yenileme ve router envanter zamanı ölçüm zamanı sayılmaz.</p>
  <p>Güncel: en fazla 5 dakikalık güvenilir gözlem · Eski: 5 dakikayı aşan gözlem · Bilinmiyor: güvenilir ölçüm zamanı yok.</p>
  <PppoeObservations isDemo={data.is_demo}/>
  <p><a className="text-link" href="#module=routers">Router Merkezi</a> · <a className="text-link" href="#module=subscribers">Abone Detay için abone seç</a></p>
 </section>;
}
