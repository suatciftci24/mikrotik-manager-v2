import { useSyncExternalStore } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';

type Preference = 'light' | 'dark' | 'system';
declare global {
  interface Window {
    v2Theme: {getPreference: () => Preference; setPreference: (value: Preference) => void};
  }
}
const subscribe = (listener: () => void) => {
  window.addEventListener('v2-theme-change', listener);
  return () => window.removeEventListener('v2-theme-change', listener);
};
const options = [
  {value: 'light', label: 'Beyaz tema', text: 'Beyaz', Icon: Sun},
  {value: 'dark', label: 'Gece teması', text: 'Gece', Icon: Moon},
  {value: 'system', label: 'Sistem teması', text: 'Sistem', Icon: Monitor},
] as const;
export function ThemePicker() {
  const preference = useSyncExternalStore(subscribe, window.v2Theme.getPreference);
  return <div className="theme-picker" role="group" aria-label="Tema seçimi">{options.map(({value, label, text, Icon}) =>
    <button key={value} type="button" className="theme-option" aria-label={label} title={label} aria-pressed={preference === value} onClick={() => window.v2Theme.setPreference(value)}><Icon size={15}/><span>{text}</span></button>
  )}</div>;
}
