import {expiryInfo} from './expiry.ts';
import type {RadiusRecord,RadiusScope} from './radiusVisibility.ts';

export const transitionLabels={PRECHECK:'Ön incelemeye uygun',MISSING:'Eksik bilgi',CONFLICT:'Çakışma riski',LIVE:'Canlı doğrulama gerekli'} as const;
export type TransitionClass=keyof typeof transitionLabels;
export type TransitionCheck={label:string;state:'Kayıtlı'|'Eksik bilgi'|'Çakışma riski'|'Doğrulanamadı';reason:string};
export type TransitionCandidate={record:RadiusRecord;classification:TransitionClass;reasons:string[];riskKey:string;checks:TransitionCheck[]};
/** Comparison hypothesis only: never changes a username or establishes AAA identity. */
export function usernameRiskKey(username:string){return username.normalize('NFKC').trim().toLowerCase();}
/** Pure, deterministic for the supplied authorized store snapshot and Turkey date. */
export function previewLocalRadius(rows:RadiusRecord[],scope:RadiusScope,today:string){
 if(!['LEGACY','PERSISTENT'].includes(scope)||expiryInfo(today,today).status==='UNKNOWN')throw new Error('Önizleme deposu veya Türkiye günü doğrulanamadı.');
 const ids=new Map<string,number>(),names=new Map<string,Set<string>>();
 for(const row of rows){
  ids.set(row.id,(ids.get(row.id)??0)+1);
  const key=usernameRiskKey(row.username);if(!key)continue;
  const group=names.get(key)??new Set<string>();group.add(row.id);names.set(key,group);
 }
 const seen=new Set<string>(),candidates:TransitionCandidate[]=[];
 for(const row of rows){
  if(row.authority!=='LOCAL'||seen.has(row.id))continue;
  seen.add(row.id);
  const missing:string[]=[],risks:string[]=[],live:string[]=[],checks:TransitionCheck[]=[];
  const check=(label:string,ok:boolean,reason:string)=>{checks.push({label,state:ok?'Kayıtlı':'Eksik bilgi',reason:ok?'Yerel GET kaydında mevcut; dış sistem doğrulaması değildir.':reason});if(!ok)missing.push(reason);};
  check('Hesap kimliği / revizyon',row.id.startsWith(scope==='PERSISTENT'?'demo-managed-sub-':'demo-sub-')&&Number.isInteger(row.revision)&&row.revision>=(scope==='PERSISTENT'?1:0),'Aynı depodaki sentetik hesap kimliği ve depo sözleşmesine uygun revizyon gerekli.');
  check('Router referansı',!!row.routerId?.startsWith(scope==='PERSISTENT'?'demo-managed-router-':'demo-router-')&&!!row.routerName?.trim(),'Kayıtlı router ID/adı eksik veya kapsam dışı; NAS bağı tahmin edilmez.');
  check('Erişim türü',row.access==='PPPOE'||row.access==='HOTSPOT','PPPoE / Hotspot türü kayıtlı olmalı; LOCAL kaynaktan tür türetilmez.');
  check('Paket adı',!!row.plan.trim(),'Yerel paket adı eksik; AAA profili tahmin edilmez.');
  check('Bitiş tarihi',expiryInfo(row.expiresOn,today).status!=='UNKNOWN','Kayıtlı ve geçerli bitiş tarihi gerekli.');
  check('Hesap durumu',['ACTIVE','PAUSED','PENDING'].includes(row.status),'Yerel hesap durumu bilinmiyor.');
  const parts=row.username.split('@'),validUsername=!!row.username.trim()&&!/\s|[\x00-\x1f\x7f]/.test(row.username)&&parts.length<=2&&parts.every(Boolean);
  check('Kullanıcı adı',validUsername,'Kullanıcı adı boş, boşluk/kontrol karakterli veya realm biçimi belirsiz.');
  if((ids.get(row.id)??0)>1)risks.push('Seçili yetkili depo snapshot’ında hesap kimliği birden çok kez bulundu.');
  const riskKey=usernameRiskKey(row.username);
  if((names.get(riskKey)?.size??0)>1)risks.push('Yetkili kayıtlarda aynı NFKC/küçük harf kullanıcı-realm risk anahtarı var; gerçek kimlik eşitliği politikaya bağlı.');
  if(risks.length)checks.push({label:'Yerel kimlik çakışması',state:'Çakışma riski',reason:risks.join(' ')});
  else checks.push({label:'Yerel kimlik çakışması',state:'Kayıtlı',reason:'Yalnız bu depodaki erişilebilir kayıtlarda aynı risk anahtarı görülmedi; diğer depolar ve gerçek RADIUS sorgulanmadı.'});
  if(parts.length!==2)live.push('Hedef realm kayıtlı değil; varsayılan realm atanmadı.');
  if(row.username!==riskKey||/[^\x21-\x7e]/.test(row.username))live.push('Büyük/küçük harf, Unicode ve realm/IDNA politikası kararlaştırılmalı; kullanıcı adı değiştirilmedi.');
  if(row.expiresOn&&expiryInfo(row.expiresOn,today).status==='EXPIRED')live.push('Bitiş geçmişte; AAA expiration ve hesap politikası kararı gerekli.');
  if(row.status==='PENDING')live.push('Bekleyen hesabın geçiş politikası belirlenmeli.');
  checks.push(...[
   {label:'Merkezi abonelik kimliği',reason:'Doğrulanamadı: mevcut GET ayrı merkezi abonelik kimliği taşımıyor; hesap ID’si bunun yerine geçirilmez.'},
   {label:'Realm / canlı kullanıcı çakışması',reason:'Doğrulanamadı: hedef realm ve sunucu namespace’i bağlı değil.'},
   {label:'NAS / router eşlemesi',reason:'Doğrulanamadı: router referansı doğrulanmış NAS-Identifier değildir.'},
   {label:'AAA profil / süre eşlemesi',reason:'Doğrulanamadı: paket adı ve kayıtlı tarih AAA attribute/Expiration kanıtı değildir.'},
   {label:'Geçiş yetkisi / audit',reason:'Doğrulanamadı: kayıt okuma yetkisi taşıma yetkisi vermez; geçiş audit’i oluşturulmadı.'},
  ].map(check=>({...check,state:'Doğrulanamadı' as const})));
  const classification:TransitionClass=risks.length?'CONFLICT':missing.length?'MISSING':live.length?'LIVE':'PRECHECK';
  candidates.push({record:row,classification,reasons:[...risks,...missing,...live,...(!risks.length&&!missing.length&&!live.length?['Yerel alanlar ön inceleme için yeterli; tüm canlı kontroller ayrıca doğrulanmalı.']:[])],riskKey,checks});
 }
 const counts:Record<TransitionClass,number>={PRECHECK:0,MISSING:0,CONFLICT:0,LIVE:0};
 for(const candidate of candidates)counts[candidate.classification]++;
 return {candidates,total:candidates.length,counts};
}
