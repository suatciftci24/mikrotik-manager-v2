/** Reusable, credential-free defaults. Trust and target identity remain per router. */
export type RouterConnectionProfile = Readonly<{
 id:string;label:string;port:'8729';versionHint:string;
 transport:'API_SSL';verifyChain:true;verifyIpSan:true;requireLeafPin:true;readOnly:true;
}>;
const security={port:'8729',transport:'API_SSL',verifyChain:true,verifyIpSan:true,requireLeafPin:true,readOnly:true} as const;
export const routerConnectionProfiles:readonly RouterConnectionProfile[]=Object.freeze([
 Object.freeze({...security,id:'api-ssl-auto',label:'API-SSL · Sürümü otomatik algıla',versionHint:'RouterOS 6.49.x veya 7.x'}),
 Object.freeze({...security,id:'api-ssl-ros6',label:'API-SSL · RouterOS 6.49.x',versionHint:'Tam sürüm isteğe bağlıdır; cihazdan okunur.'}),
 Object.freeze({...security,id:'api-ssl-ros7',label:'API-SSL · RouterOS 7.x',versionHint:'Tam sürüm isteğe bağlıdır; cihazdan okunur.'}),
]);
export function connectionProfile(id:string):RouterConnectionProfile{
 const profile=routerConnectionProfiles.find(value=>value.id===id);
 if(!profile)throw new Error('Bağlantı profili bulunamadı.');
 return profile;
}
