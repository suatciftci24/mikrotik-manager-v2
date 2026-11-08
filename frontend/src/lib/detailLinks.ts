/** Bounded same-app return context. No external URL or recursive return chain. */
export function detailReturnHash(hash:string){
 if(hash.length>4000||!hash.startsWith('#'))return null;
 const params=new URLSearchParams(hash.slice(1));
 const module=params.get('module');
 const detail=['routers','subscribers'].includes(module??'')&&!!params.get('id');
 const report=module==='dashboard'&&['DAILY_REPORT','OPERATIONS_REPORT'].includes(params.get('view')??'');
 const subscriberList=module==='subscribers'&&['LEGACY','PERSISTENT','HISTORY'].includes(params.get('workspace')??'');
 if(!detail&&!report&&!subscriberList&&module!=='operations'&&module!=='mikajani')return null;
 params.delete('return_to');return '#'+params.toString();
}
export function linkedDetailHash(target:{module:'routers'|'subscribers';id:string;source?:string;workspace?:string},fromHash=''){
 const params=new URLSearchParams({module:target.module,id:target.id});if(target.source)params.set('source',target.source);if(target.workspace)params.set('workspace',target.workspace);const back=detailReturnHash(fromHash);
 if(back)params.set('return_to',back);
 return '#'+params.toString();
}

/** A validated center return is a single level, just like detail links. */
export function linkedCenterHash(target:string,fromHash=''){
 const params=new URLSearchParams(target.replace(/^#/,''));params.delete('return_to');
 const back=detailReturnHash(fromHash);if(back)params.set('return_to',back);
 return '#'+params;
}
export function centerReturnHash(hash:string){return detailReturnHash(new URLSearchParams(hash.replace(/^#/,'')).get('return_to')??'');}
