/** One read at a time, with a fixed 60s cadence. No transport or credentials here. */
export function inventoryRefresh<T>({load,publish,schedule=setInterval,cancel=clearInterval,now=Date.now}:{
 load:(signal:AbortSignal)=>Promise<T>;
 publish:(state:{data?:T;loading:boolean;error?:string;lastSuccess:number|null})=>void;
 schedule?:typeof setInterval;cancel?:typeof clearInterval;now?:()=>number;
}){
 let stopped=false, controller:AbortController|null=null, lastSuccess:number|null=null;
 const refresh=async()=>{
  if(stopped||controller)return;
  const request=new AbortController();controller=request;
  publish({loading:true,lastSuccess});
  try{
   const data=await load(request.signal);
   if(!stopped){lastSuccess=now();publish({data,loading:false,lastSuccess});}
  }catch{
   if(!stopped)publish({loading:false,error:'Envanter yenilenemedi. Son başarılı veriler gösterilmiyor.',lastSuccess});
  }finally{if(controller===request)controller=null;}
 };
 const timer=schedule(()=>void refresh(),60_000);
 void refresh();
 return {refresh:()=>void refresh(),stop:()=>{stopped=true;cancel(timer);controller?.abort();}};
}
