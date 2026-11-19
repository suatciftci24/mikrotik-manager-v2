import {ApiError} from './api';

export function subscriberOperationConflict(detail:string){
 const message=detail.toLocaleLowerCase('tr-TR');
 if(/(?:istek|işlem) kimliği.*(?:başka|farklı|kullanılmış)|tekrarlanan abone veya (?:istek|işlem) kimliği/.test(message))
  return 'İstek kimliği daha önce kullanılmış veya listede yineleniyor. İşlem geçmişini kontrol edin. Güncelleme gerekiyorsa güncel kayıtlardan yeni önizleme oluşturun.';
 if(/eski sonuçları eksik/.test(message))
  return 'Bu grubun önceki sonuçları eksik. Yeniden işlem yapmadan önce geçmişi ve abonelerin güncel durumunu kontrol edin.';
 if(/revizyon|revision|conflict|önizlemeden sonra|kayıt değişmiş|önizlemesi değiş/.test(message))
  return 'Kayıt değişmiş. Güncel aboneyi açıp yeni önizleme oluşturun.';
}

export function subscriberOperationError(failure:unknown){
 if(failure instanceof ApiError&&failure.status===401)return 'Oturumunuz sona ermiş olabilir. Yeniden giriş yapın; ardından mevcut isteğin sonucunu doğrulayın.';
 if(failure instanceof ApiError&&failure.status===403)return 'Bu işlem veya sonuç kaydı için yetkiniz yok. Yetkilerinizi kontrol edin.';
 if(failure instanceof ApiError&&[409,422].includes(failure.status))
  return subscriberOperationConflict(failure.message)??failure.message;
 if(failure instanceof SyntaxError)return 'Sunucudan doğrulanabilir işlem yanıtı alınamadı.';
 if(failure instanceof Error&&(failure.name==='AbortError'||failure.message==='Failed to fetch'||failure.message==='Load failed'))return 'İşlem yanıtı alınamadı. Bağlantıyı kontrol edin ve aynı isteğin sonucunu doğrulayın.';
 return failure instanceof Error?failure.message:'İşlem sonucu alınamadı.';
}
