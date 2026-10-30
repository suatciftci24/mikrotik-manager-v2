export type OperatorCandidate={id:string;revision:number;source:'V2_AUTHENTICATED_SESSION'};
export type PilotIdentity={state:'ELIGIBLE'|'BOOTSTRAP_DEMO'|'DEMO_ACCOUNT'|'INACTIVE'|'UNVERIFIED'|'NOT_ADMIN'|'INSUFFICIENT_SCOPE';candidate:OperatorCandidate|null};
const messages:Record<string,string>={
 BOOTSTRAP_DEMO:'Bu oturum varsayılan Demo Operatör hesabıdır. Sistem Yöneticisi rolü sentetik yönetim içindir; gerçek pilot operatör ID’si gösterilmez ve bu hesaba pilot yetkisi verilemez.',
 DEMO_ACCOUNT:'Bu hesap sentetik demo kökenlidir; gerçek ADMIN veya pilot operatörü olarak kullanılamaz. İlk gerçek ADMIN yalnız yetkili yerel operatörün gizli terminal kurulumu ile oluşturulur.',
 INACTIVE:'Hesap etkin değil; pilot operatörü olarak kullanılamaz.',
 NOT_ADMIN:'Bu oturum ADMIN değildir; pilot operatör ID’si gösterilmez.',
 INSUFFICIENT_SCOPE:'ADMIN rolü var ancak merkezi yönetim kapsamı eksik. Rol adı tek başına pilot uygunluğu sağlamaz.',
 UNVERIFIED:'Doğrulanmış operatör durumu alınamadı. Oturum bilgisini mevcut API’den yenileyin; görünen ad veya rol adından ID türetilmez.',
};
export function pilotOperatorView(identity?:PilotIdentity|null):{eligible:boolean;id:string|null;message:string;state:string}{
 const candidate=identity?.candidate;
 const valid=identity?.state==='ELIGIBLE'&&candidate?.source==='V2_AUTHENTICATED_SESSION'&&typeof candidate.id==='string'&&candidate.id.trim().length>0&&candidate.id===candidate.id.trim()&&candidate.id.length<=80&&!/[\x00-\x1f\x7f]/.test(candidate.id)&&candidate.id!=='demo-user'&&Number.isInteger(candidate.revision)&&candidate.revision>=0;
 if(valid)return {eligible:true,id:candidate.id,state:'ELIGIBLE',message:'Kayıtlı, aktif ve tam yetkili V2 ADMIN oturumu doğrulandı.'};
 const state=identity?.state&&identity.state!=='ELIGIBLE'&&messages[identity.state]?identity.state:'UNVERIFIED';
 return {eligible:false,id:null,state,message:messages[state]};
}
