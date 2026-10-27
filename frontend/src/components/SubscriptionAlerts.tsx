import type { ExpiryFilter } from '../lib/expiry';
import type { SubscriptionAlertSummary } from '../lib/subscriptionAlerts';

export function SubscriptionAlerts({summary,selected,onSelect}:{summary:SubscriptionAlertSummary;selected:ExpiryFilter;onSelect:(filter:ExpiryFilter)=>void}) {
  const cards=[
    {filter:'EXPIRED',label:'Süresi dolmuş',count:summary.expired,tone:'expired',note:'Bitişi bugünden önce'},
    {filter:'TODAY',label:'Bugün dolacak',count:summary.today,tone:'today',note:'Bugünün sonuna kadar geçerli'},
    {filter:'WITHIN_3',label:'3 gün içinde dolacak',count:summary.within_3,tone:'within_3',note:'Bugün dahil: 0–3 gün'},
    {filter:'WITHIN_7',label:'7 gün içinde dolacak',count:summary.within_7,tone:'within_7',note:'Bugün dahil: 0–7 gün'},
  ] as const;
  return <section className="panel subscription-alerts" aria-labelledby="subscription-alert-title">
    <div className="panel-title"><h2 id="subscription-alert-title">Abonelik Takip ve Uyarı Merkezi</h2><span className="demo-chip">SENTETİK</span></div>
    <p className="daily-description">Mevcut arama, router, kaynak, paket ve hesap durumu filtreleriyle eşleşen {summary.total} abone. Bitiş filtresi kartların kapsamını daraltmaz; kart seçimi aşağıdaki listeyi filtreler. Türkiye takvim günü esas alınır.</p>
    <div className="subscription-alert-grid">{cards.map(card=><button key={card.filter} className={`subscription-alert-card expiry-${card.tone}`} aria-pressed={selected===card.filter} onClick={()=>onSelect(card.filter)}>
      <span>{card.label}</span><strong>{card.count}</strong><small>{card.note}</small>
    </button>)}</div>
    <p className="daily-description" role="status">Tekil uyarı toplamı: <strong>{summary.warning}</strong>. Süresi dolmuş veya en fazla 7 günü kalmış aboneler bir kez sayılır. Bugün, 3 gün ve 7 gün kartları iç içedir; sayıları toplanmaz.</p>
    <div className="subscription-alert-links">
      <button className="button-secondary" aria-pressed={selected==='WITHIN_30'} onClick={()=>onSelect('WITHIN_30')}>30 gün içinde (bugün dahil): {summary.within_30}</button>
      <button className="button-secondary" aria-pressed={selected==='VALID'} onClick={()=>onSelect('VALID')}>Süresi geçerli: {summary.valid}</button>
      <button className="button-secondary" aria-pressed={selected==='UNKNOWN'} onClick={()=>onSelect('UNKNOWN')}>Bitiş tarihi yok / geçersiz: {summary.unknown}</button>
      <button className="button-secondary" aria-pressed={selected==='ALL'} onClick={()=>onSelect('ALL')}>Tüm bitiş durumları: {summary.total}</button>
    </div>
    {summary.total===0&&<p className="missing-data">Veri yok. Mevcut arama ve diğer filtrelerle eşleşen demo abone bulunmuyor.</p>}
    {summary.unknown>0&&<p className="daily-description">Bitiş tarihi bilinmeyen {summary.unknown} kayıt, süresi dolmuş veya süresi geçerli sayılmaz; kalan gün tahmin edilmez.</p>}
    <p className="daily-description">Yalnız kaydedilmiş demo bitiş tarihleri değerlendirilir. Uyarılar gerçek hesaba müdahale etmez, otomatik devre dışı bırakmaz veya dış bildirim göndermez. Yenilemek için listeden mevcut abone detayını açın.</p>
  </section>;
}
