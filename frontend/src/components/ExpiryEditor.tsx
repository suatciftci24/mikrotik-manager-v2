import { useEffect, useRef, useState, type FormEvent } from 'react';
import { invalidateResources } from '../lib/resourceEvents';
import { api, type Subscriber, type SubscriberDetailData } from '../lib/api';
import { expiryDate, expiryInfo } from '../lib/expiry';
import { subscriberSource } from '../lib/source';
import { Facts } from './Resource';
import { SourceBadge } from './Status';

type Review = {expires_on: string; operation: 'RENEWAL' | 'DATE_EDIT'; request_id: string};
export function ExpiryEditor({subscriber, today, onClose, onSaved, persistence}: {
  subscriber: Subscriber; persistence: SubscriberDetailData['persistence']; today: string; onClose: () => void; onSaved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [value, setValue] = useState('');
  const [operation, setOperation] = useState<'RENEWAL' | 'DATE_EDIT'>(subscriber.expires_on ? 'RENEWAL' : 'DATE_EDIT');
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const sending = useRef(false);
  const source = subscriberSource(subscriber.source);
  useEffect(() => {
    const origin = document.activeElement as HTMLElement | null;
    const node=dialog.current;node?.showModal();
    return () => { node?.close(); if(origin?.isConnected)origin.focus({preventScroll: true}); };
  }, []);
  useEffect(() => { dialog.current?.querySelector<HTMLElement>(review?'h2':'form input, form select')?.focus(); }, [review]);
  const prepare = (event: FormEvent) => {
    event.preventDefault(); setError('');
    const info = expiryInfo(value, today);
    if (info.days === null) { setError('Geçerli bir yeni bitiş tarihi girin.'); return; }
    if (info.days < 0) { setError('Yeni bitiş tarihi Türkiye gününe göre geçmişte olamaz.'); return; }
    if (value === subscriber.expires_on) { setError('Yeni tarih mevcut tarihten farklı olmalıdır.'); return; }
    if (operation === 'RENEWAL' && (!subscriber.expires_on || value <= subscriber.expires_on)) { setError('Yenileme için mevcut tarihten daha ileri bir tarih seçin.'); return; }
    setReview({expires_on: value, operation, request_id: crypto.randomUUID()});
  };
  const save = async () => {
    if (!review || sending.current || source === 'UNKNOWN' || persistence !== 'local-postgresql-demo') return;
    sending.current = true; setPending(true); setError('');
    try {
      const result = await api<SubscriberDetailData>(`/subscribers/${encodeURIComponent(subscriber.id)}/demo-expiry`, {
        method: 'POST', headers: {'X-V2-Demo-Action': 'expiry'},
        body: JSON.stringify({...review, expected_expires_on: subscriber.expires_on, expected_revision: subscriber.revision, expected_source: source, confirmed: true}),
      });
      if (result.persistence !== 'local-postgresql-demo') throw new Error('Kalıcı demo kaydı doğrulanamadı; güncel kaydı yeniden yükleyin.');
      onSaved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Demo değişikliği tamamlanamadı.'); }
    finally { sending.current = false; setPending(false); }
  };
  return <dialog ref={dialog} className="expiry-dialog" aria-busy={pending} aria-labelledby="expiry-editor-title" aria-describedby="expiry-editor-demo" onCancel={event => {event.preventDefault(); if (!sending.current) onClose();}}>
    <h2 id="expiry-editor-title" tabIndex={-1}>{review ? 'Demo değişikliğini onaylayın' : 'Demo bitiş tarihini düzenle / yenile'}</h2>
    <p id="expiry-editor-demo">Bu işlem yalnız V2 yerel geliştirme veritabanındaki sentetik demo kaydını günceller. Tarih ve geçmiş sayfa yenilemesi ve uygulama yeniden açılması sonrasında korunur; gerçek abonelik değişmez.</p>
    <p><strong>{subscriber.customer_name}</strong> · <SourceBadge source={subscriber.source}/></p>
    {persistence !== 'local-postgresql-demo' ? <p className="form-error" role="alert">Kalıcı demo saklama etkin değil; güncel yerel API ile yeniden açılmalı.</p> : source === 'UNKNOWN' ? <p className="form-error" role="alert">Kaynak bilinmiyor; kaynak doğrulanmadan değişiklik yapılamaz.</p> : review ? <>
      <Facts items={[["İşlem türü", review.operation === 'RENEWAL' ? 'Yenileme (demo)' : 'Bitiş tarihi düzenleme (demo)'], ["Mevcut bitiş tarihi", expiryDate(subscriber.expires_on)], ["Yeni bitiş tarihi", expiryDate(review.expires_on)]]}/>
      <p>Tarih, Türkiye takviminde belirtilen günün sonuna kadar geçerlidir. Kaynak ve aktif/duraklatılmış hesap durumu bu tarih işlemiyle değiştirilmez.</p>
      {error && <p className="form-error" role="alert">{error} Sonuç alınamadıysa aynı onayı yeniden gönderebilirsiniz; aynı işlem iki kez uygulanmaz.</p>}
      {error && <button className="button-secondary" disabled={pending} onClick={()=>{onClose();invalidateResources(['/subscribers','/routers']);}}>Güncel kaydı yeniden yükle</button>}
      <div className="expiry-editor-actions"><button className="button-secondary" disabled={pending} onClick={() => {setReview(null);setError('');}}>Tarihi düzelt</button><button className="button-primary" disabled={pending} onClick={save}>{pending ? 'Demo kaydı güncelleniyor…' : 'Onayla ve demo kaydını güncelle'}</button></div>
    </> : <form onSubmit={prepare} noValidate>
      <label className="form-label">İşlem türü<select aria-label="İşlem türü" value={operation} onChange={e => setOperation(e.target.value as Review['operation'])}><option value="RENEWAL" disabled={!subscriber.expires_on}>Yenileme</option><option value="DATE_EDIT">Bitiş tarihi düzenleme</option></select></label>
      <p>Mevcut bitiş tarihi: <strong>{expiryDate(subscriber.expires_on)}</strong></p>
      <label className="form-label">Yeni bitiş tarihi<input autoFocus type="date" required min={today} value={value} onChange={e => {setValue(e.target.value);setError('');}}/></label>
      <p>Bugün veya ileri bir tarih seçin (Türkiye). Yenileme mevcut tarihi ileri alır; tarih düzenleme bugünden önceye gidemez.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="button-primary" type="submit">Değişikliği gözden geçir</button>
    </form>}
    <button className="button-secondary expiry-editor-cancel" disabled={pending} onClick={onClose}>İptal</button>
  </dialog>;
}
