export const V26_HTTP_API_BASE='http://127.0.0.1:18996';

export function requireV26AcceptanceReadiness(status,payload){
 if(status!==200||!payload||payload.service!=='mikrotik-manager-v2'||
    payload.environment!=='v26-acceptance'||payload.runtime_profile!=='v26-isolated-acceptance'||
    payload.api_port!==18996||payload.database_checked!==false){
  throw new Error('BLOCKED: V2.6 acceptance runtime profile was not verified from the isolated HTTP service');
 }
 return payload;
}
