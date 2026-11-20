import {useEffect,useState} from 'react';

export function useSettledSearch(value:string){
 const [settled,setSettled]=useState(value);
 useEffect(()=>{
  if(settled===value)return;
  const timer=setTimeout(()=>setSettled(value),250);
  return ()=>clearTimeout(timer);
 },[value,settled]);
 return [settled,settled!==value] as const;
}
