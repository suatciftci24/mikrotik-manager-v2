export type SubscriberPhoto={id:string;created_at:string;size_bytes:number;media_type:'image/jpeg'};
export type SubscriberPhotoCollection={subscriber_id:string;source:'LOCAL'|'RADIUS';access_type:'PPPOE'|'HOTSPOT';items:SubscriberPhoto[];is_demo:true};
export function subscriberPhotosPath(id:string){return '/subscriber-center/'+encodeURIComponent(id)+'/photos';}
export function assertSubscriberPhotos(value:SubscriberPhotoCollection,id:string,source:'LOCAL'|'RADIUS',accessType:'PPPOE'|'HOTSPOT'){
 if(!value||value.is_demo!==true||value.subscriber_id!==id||value.source!==source||value.access_type!==accessType||!Array.isArray(value.items)||value.items.length>20)throw new Error('Abone fotoğraf kaynağı doğrulanamadı.');
 const seen=new Set<string>();
 for(const item of value.items){if(!item||!/^[0-9a-f]{32}$/.test(item.id)||seen.has(item.id)||item.media_type!=='image/jpeg'||!Number.isInteger(item.size_bytes)||item.size_bytes<1||item.size_bytes>8*1024*1024||!Number.isFinite(Date.parse(item.created_at)))throw new Error('Fotoğraf kayıt bilgisi doğrulanamadı.');seen.add(item.id);}
 return value;
}
export function subscriberPhotoImagePath(id:string,photoId:string,variant:'thumbnail'|'full'){
 if(!/^[0-9a-f]{32}$/.test(photoId))throw new Error('Fotoğraf kimliği geçersiz.');
 return subscriberPhotosPath(id)+'/'+photoId+'?variant='+variant;
}
