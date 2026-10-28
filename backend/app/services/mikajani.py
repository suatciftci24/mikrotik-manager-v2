"""Pure, deterministic observation replay. No DB/device/AI access or action executor."""
from datetime import datetime, timedelta, timezone
from uuid import uuid5, NAMESPACE_URL
from app.schemas.mikajani import Observation, Finding, Transition, RouterHealth, Analysis

STALE = timedelta(minutes=15)
RECOVERY = timedelta(seconds=60)
RULES = {
    'ROUTER': ('P2', 'Router çevrimdışı gözlemi', 'Tek router erişim gözlemi; cihaz arızası kanıtlanmış değildir.', 'Bağımsız bir noktadan erişim ve son kayıt zamanını inceleyin.', 'MEDIUM'),
    'WAN': ('P2', 'WAN / internet gözlem sorunu', 'Sentetik internet kesintisi veya WAN değişikliği kaydedildi.', 'WAN, default route ve kaynak gözlem dizisini inceleyin.', 'MEDIUM'),
    'IPSEC': ('P2', 'IPsec bağlantı kaybı', 'Açık sentetik tünel durum gözlemi bağlantı kaybı bildiriyor.', 'Tünel uçları ve bağlantı geçmişini yetkili operatör incelemeli.', 'HIGH'),
    'PPPOE': ('P3', 'PPPoE oturum anomalisi', 'Aynı sentetik raporda bir abone için birden fazla aktif oturum var.', 'Oturum kimliklerini ve rapor zamanını inceleyin; hesap durumunu tek başına oturum saymayın.', 'MEDIUM'),
    'MONITOR': ('P3', 'İzleme erişimi belirsiz', 'İzleme noktasından veri toplama sorunu bildirildi.', 'İzleme kaynağını bağımsız noktadan doğrulayın.', 'LOW'),
    'DATA': ('P4', 'Veri güncelliği sorunu', 'Gözlem eksik, belirsiz veya 15 dakikadan eski; canlı sağlık çıkarılamaz.', 'Yeni, zaman damgalı ve bağımsız gözlem sağlayın.', 'LOW'),
    'CORRELATION': ('P1', 'Olası ortak erişim sorunu', '120 saniye içinde en az iki router için erişim kaybı gözlendi. Ortak izleme veya ağ yolu sorunu olabilir; kesin kök neden değildir.', 'Önce ortak izleme noktasını ve bağımsız erişim kanıtını doğrulayın; ardından router bazlı inceleyin.', 'LOW'),
}


def analyze(routers, raw_observations, now, source='saved-demo'):
    if now.utcoffset() is None:
        raise ValueError('Analysis time requires timezone')
    if any(r.get('is_demo') is not True for r in routers):
        raise ValueError('Synthetic routers required')
    names = {r['id']: r['name'] for r in routers}
    if len(names) != len(routers):
        raise ValueError('Duplicate router identity')
    observations = {}
    for raw in raw_observations:
        row = Observation.model_validate(raw)
        if row.router_id not in names or row.observed_at > now:
            raise ValueError('Unknown router or future observation')
        if row.id in observations and observations[row.id] != row:
            raise ValueError('Conflicting observation identity')
        observations[row.id] = row
    ordered = sorted(observations.values(), key=lambda r: (r.observed_at, r.id))
    # Equal-time contradictory values must not turn into an arbitrary diagnosis.
    slots = {}
    for row in ordered:
        key = (row.router_id, row.domain, row.subject_id, row.observed_at)
        if key in slots and slots[key] != row.status:
            raise ValueError('Conflicting simultaneous observations')
        slots[key] = row.status
    latest = {}
    session_signals = {}
    findings, opened = [], {}

    def apply(key, domain, status, at, evidence, ids, affected):
        finding = opened.get(key)
        if status == 'BAD' and finding is None:
            priority, title, reason, recommendation, confidence = RULES[domain]
            finding = Finding(id='mika-'+str(uuid5(NAMESPACE_URL, f'{source}/{key}/{at.isoformat()}/{ids[0]}')),
                domain=domain, priority=priority, state='OPEN', title=title, reason=reason,
                evidence=evidence, affected_router_ids=sorted(affected), recommendation=recommendation,
                confidence=confidence, opened_at=at, updated_at=at,
                history=[Transition(state='OPEN', occurred_at=at, evidence=evidence, observation_ids=ids)])
            opened[key] = finding
            findings.append(finding)
            return
        if finding is None:
            return
        state = None
        if status == 'GOOD':
            if finding.state != 'RECOVERING':
                state = 'RECOVERING'
            elif at - finding.history[-1].occurred_at >= RECOVERY:
                state = 'RESOLVED'
        elif status == 'UNKNOWN':
            # Missing evidence interrupts recovery; it cannot prove a recovery.
            if finding.state == 'RECOVERING' or finding.evidence != evidence:
                state = 'UPDATED'
                finding.confidence = 'LOW'
        elif finding.state == 'RECOVERING' or finding.evidence != evidence or finding.affected_router_ids != sorted(affected):
            state = 'UPDATED'
        if state:
            finding.state, finding.updated_at, finding.evidence = state, at, evidence
            finding.affected_router_ids = sorted(set(finding.affected_router_ids) | set(affected))
            finding.history.append(Transition(state=state, occurred_at=at, evidence=evidence, observation_ids=ids))
            if state == 'RESOLVED':
                finding.resolved_at = at
                del opened[key]

    # Inject deterministic freshness gaps; GET frequency never supplies recovery evidence.
    timeline = list(ordered)
    for router_id in names:
        rows = [r for r in ordered if r.router_id == router_id]
        times = sorted({r.observed_at for r in rows})
        for i, at in enumerate(times):
            end = times[i+1] if i+1 < len(times) else now
            if end - at > STALE:
                timeline.append(Observation(id=f'freshness-{router_id}-{at.isoformat()}', router_id=router_id,
                    domain='DATA', status='BAD', observed_at=at+STALE,
                    evidence='Son kaynak gözlemi: '+at.isoformat()+'; 15 dakika yeni veri yok.'))
        for at in times:
            timeline.append(Observation(id=f'fresh-{router_id}-{at.isoformat()}', router_id=router_id,
                domain='DATA', status='GOOD', observed_at=at, evidence='Yeni zaman damgalı gözlem alındı.'))
    timeline.sort(key=lambda r: (r.observed_at, r.id))
    correlated = set()
    for row in timeline:
        latest[row.router_id, row.domain] = row
        if row.domain == 'PPPOE':
            session_signals[row.router_id, row.subject_id] = row
        status = 'BAD' if row.status == 'UNKNOWN' and row.domain == 'DATA' else row.status
        apply((row.router_id, row.domain, row.subject_id), row.domain, status, row.observed_at, row.evidence, [row.id], [row.router_id])
        if row.status == 'UNKNOWN' and row.domain != 'DATA':
            apply((row.router_id, 'UNKNOWN-'+row.domain, row.subject_id), 'DATA', 'BAD', row.observed_at,
                  f'{row.domain}: belirsiz gözlem — {row.evidence}', [row.id], [row.router_id])
        elif row.domain != 'DATA':
            apply((row.router_id, 'UNKNOWN-'+row.domain, row.subject_id), 'DATA', 'GOOD', row.observed_at,
                  f'{row.domain}: açık durum gözlemi alındı.', [row.id], [row.router_id])
        if row.domain != 'ROUTER':
            continue
        failed = [r for (rid, domain), r in latest.items() if domain == 'ROUTER' and r.status == 'BAD'
                  and timedelta(0) <= row.observed_at-r.observed_at <= timedelta(seconds=120)]
        if len(failed) >= 2:
            correlated.update(r.router_id for r in failed)
            apply(('network', 'CORRELATION'), 'CORRELATION', 'BAD', row.observed_at,
                  'Yakın zamanlı erişim kaybı: '+', '.join(sorted(r.router_id for r in failed)),
                  sorted(r.id for r in failed), sorted(correlated))
        elif correlated:
            recovered = [latest.get((rid, 'ROUTER')) for rid in correlated]
            good = all(r and r.status == 'GOOD' and row.observed_at-r.observed_at <= STALE for r in recovered)
            apply(('network', 'CORRELATION'), 'CORRELATION', 'GOOD' if good else 'UNKNOWN', row.observed_at,
                  'İlişkili routerlar için iyi gözlemler var.' if good else 'Ortak neden için yeterli bağımsız kanıt yok.',
                  [row.id], sorted(correlated))
            if ('network', 'CORRELATION') not in opened:
                correlated.clear()
    health = []
    for rid, name in names.items():
        rows = [r for r in ordered if r.router_id == rid]
        last = max((r.observed_at for r in rows), default=None)
        reliability = 'MISSING' if last is None else 'STALE' if now-last > STALE else 'CURRENT'
        signals = {}
        for domain in ('ROUTER', 'WAN', 'IPSEC', 'PPPOE', 'MONITOR'):
            row = latest.get((rid, domain))
            signals[domain] = row.status if row and now-row.observed_at <= STALE else 'UNKNOWN'
            if domain == 'PPPOE':
                states = [s.status if now-s.observed_at<=STALE else 'UNKNOWN' for (owner, _), s in session_signals.items() if owner==rid]
                signals[domain] = 'BAD' if 'BAD' in states else 'UNKNOWN' if not states or 'UNKNOWN' in states else 'GOOD'
        state = 'ATTENTION' if 'BAD' in signals.values() else 'UNKNOWN' if reliability != 'CURRENT' or 'UNKNOWN' in signals.values() else 'HEALTHY'
        health.append(RouterHealth(router_id=rid, name=name, health=state, signals=signals,
                                   latest_observed_at=last, reliability=reliability))
    findings.sort(key=lambda f: (f.state == 'RESOLVED', f.priority, f.opened_at, f.id))
    active = [f for f in findings if f.state != 'RESOLVED']
    return Analysis(source=source, generated_at=datetime.now(timezone.utc), evaluated_at=now, health=health,
        events=findings, summary={'routers':len(health), 'active':len(active), 'resolved':len(findings)-len(active),
            'uncertain':sum(h.health=='UNKNOWN' for h in health), **{p:sum(f.priority==p for f in active) for p in ('P1','P2','P3','P4')}},
        operational_summary=f'{len(health)} sentetik router; {len(active)} aktif bulgu. Öneriler operatör incelemesi içindir.',
        limitations=['Salt okunur, kural tabanlı analiz; cihaz işlemi ve AI API çağrısı yok.',
            'Eksik veya eski veri sağlıklı kabul edilmez. Korelasyon kesin kök neden değildir.',
            'Geçmiş kaynak gözlemlerden yeniden üretilir; kaynakta bulunmayan geçmiş veya süre tahmin edilmez.',
            'RECOVERING sonrası RESOLVED için en az 60 saniye arayla iki ayrı iyi gözlem gerekir.'])
