import { SourceBadge } from './Status';
import { sourceDescription } from '../lib/source';

export function SourceExplanation({source}: {source: unknown}) {
  return <div className="source-explanation"><SourceBadge source={source}/><p>{sourceDescription(source)}</p><p className="source-demo-note">Sentetik demo kaydıdır. Kaynak bilgisi canlı bağlantı veya kimlik doğrulama sonucu değildir; RouterOS / FreeRADIUS bağlantısı kurulmadı.</p></div>;
}
