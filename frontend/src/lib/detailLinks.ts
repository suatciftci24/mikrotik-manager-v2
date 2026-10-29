/** Bounded same-app return context. No external URL or recursive return chain. */
export function detailReturnHash(hash:string){
 if(hash.length>4000||!hash.startsWith('#'))return null;
 const params=new URLSearchParams(hash.slice(1));
 if(!['routers','subscribers'].includes(params.get('module')??'')||!params.get('id'))return null;
 params.delete('return_to');return '#'+params.toString();
}
export function linkedDetailHash(target:{module:'routers'|'subscribers';id:string;source?:string;workspace?:string},fromHash=''){
 const params=new URLSearchParams({module:target.module,id:target.id});if(target.source)params.set('source',target.source);if(target.workspace)params.set('workspace',target.workspace);const back=detailReturnHash(fromHash);
 if(back)params.set('return_to',back);
 return '#'+params.toString();
}
