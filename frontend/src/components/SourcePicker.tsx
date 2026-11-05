import {useId,type ReactNode} from 'react';
import type {SourceOption} from '../lib/workspaceContext';

/** A native select keeps source boundaries visible without another row of navigation tabs. */
export function SourcePicker({label='Veri kaynağı',value,options,onChange,children}:{label?:string;value:string;options:readonly SourceOption[];onChange:(value:string)=>void;children?:ReactNode}) {
 const id=useId();const selected=options.find(option=>option.value===value);
 return <section className="source-picker panel" aria-label={label}>
  <div className="source-picker-controls"><label className="form-label">{label}<select value={value} onChange={event=>onChange(event.target.value)} aria-describedby={id}>{!selected&&<option value={value} disabled>Yetki gerekli</option>}{options.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></label>{children}</div>
  {selected&&<p id={id}><strong>{selected.access}</strong> · {selected.description}</p>}
 </section>;
}
