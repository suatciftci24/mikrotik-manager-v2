import {pilotOperatorView,type PilotIdentity} from '../lib/pilotOperator';

export function PilotOperatorStatus({identity,authorized}:{identity?:PilotIdentity|null;authorized?:boolean}){
 const view=pilotOperatorView(identity);
 return <section className="pilot-operator-status" aria-label="Oturum ve pilot operatörü">
  <h3>Oturum ve pilot operatörü</h3><p role="status">{view.message}</p>
  {view.eligible&&<><p>Doğrulanmış V2 operatör ID: <code>{view.id}</code></p>{authorized!==undefined&&<p>{authorized?'Sunucu operatör izin listesinde.':'Sunucu operatör izin listesine henüz eklenmemiş.'}</p>}<p>Bu bilgi yetki vermez; bağlantı kapısını açmaz. Pilot izin listesi ve açık bağlantı onayı ayrıca gereklidir.</p></>}
 </section>;
}
