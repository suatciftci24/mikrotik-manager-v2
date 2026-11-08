import {ApiError} from './api';

export function subscriberOperationError(failure:unknown){
 if(failure instanceof ApiError&&failure.status===401)return 'Oturumunuz sona ermiş olabilir. Yeniden giriş yapın; ardından mevcut isteğin sonucunu doğrulayın.';
 if(failure instanceof ApiError&&failure.status===403)return 'Bu işlem veya sonuç kaydı için yetkiniz yok. Yetkilerinizi kontrol edin.';
 if(failure instanceof SyntaxError)return 'Sunucudan doğrulanabilir işlem yanıtı alınamadı.';
 if(failure instanceof Error&&(failure.name==='AbortError'||failure.message==='Failed to fetch'||failure.message==='Load failed'))return 'İşlem yanıtı alınamadı. Bağlantıyı kontrol edin ve aynı isteğin sonucunu doğrulayın.';
 return failure instanceof Error?failure.message:'İşlem sonucu alınamadı.';
}
