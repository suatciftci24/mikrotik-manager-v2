export type RuntimeProfile='local-demo'|'v26-isolated-acceptance';
export function normalizeRuntimeProfile(value:unknown):RuntimeProfile{
 return value==='v26-isolated-acceptance'?'v26-isolated-acceptance':'local-demo';
}
export function runtimeIdentity(profile:RuntimeProfile){
 return profile==='v26-isolated-acceptance'
  ?{manager:'MANAGER V2.6',workspace:'V2.6 İzole Kabul Ortamı',tag:'V2.6 İZOLE KABUL',description:'Ayrı V2.6 kabul profili · sentetik veriler · canlı sistem bağlantısı yok.'}
  :{manager:'MANAGER V2',workspace:'Demo çalışma alanı',tag:'YEREL V2 DEMO',description:'Sentetik veriler · yerel V2 demo ortamı · canlı sistem bağlantısı yok.'};
}
