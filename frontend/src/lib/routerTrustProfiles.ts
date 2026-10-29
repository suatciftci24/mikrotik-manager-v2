import type {RouterForm} from './routerRegistry';
export type TrustProfile={id:string;revision:number;kind:'TRUST_PROFILE';fields:{name:string;management_address:string;port:number;ca_pem:string;leaf_sha256:string};device_connected:false};
export function applyTrustProfile(form:RouterForm,profile:TrustProfile):RouterForm{
 if(form.management_address&&form.management_address!==profile.fields.management_address)throw new Error('Sertifika profili farklı bir IP adresine ait. Hedefi kontrol edin.');
 return {...form,management_address:profile.fields.management_address,port:String(profile.fields.port),ca_pem:profile.fields.ca_pem,leaf_sha256:profile.fields.leaf_sha256};
}
