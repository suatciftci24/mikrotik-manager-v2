import {subscriberOperationError} from './subscriberOperationRecovery';
import {rememberPending,forgetPending} from './pendingSubscriberOperations';
import {useEffect,useRef,useState} from 'react';
import {api,ApiError} from './api';
import {invalidateResources} from './resourceEvents';

import {subscriberSaveDependencies} from './subscriberDependencies';
export {subscriberSaveDependencies} from './subscriberDependencies';
export type SubscriberSaveAttempt<T>={requestId:string;path:string;resultPath:string;body:string;header:string;matches:(result:T)=>boolean};
type State='IDLE'|'SENDING'|'UNCERTAIN'|'FAILED'|'SUCCESS';
export function useSubscriberSave<T>(onSaved:(result:T)=>void){
 const mounted=useRef(true),activeRequest=useRef<AbortController|null>(null);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;activeRequest.current?.abort();};},[]);
 const [state,setState]=useState<State>('IDLE'),[error,setError]=useState('');
 const attempt=useRef<SubscriberSaveAttempt<T>|null>(null),sending=useRef(false),outcome=useRef<State>('IDLE');
 const reset=()=>{if(['IDLE','FAILED'].includes(outcome.current)){attempt.current=null;outcome.current='IDLE';setState('IDLE');setError('');}};
 async function send(input:SubscriberSaveAttempt<T>){
  if(sending.current||outcome.current==='SUCCESS')return;
  const query=outcome.current==='UNCERTAIN';
  attempt.current??=input;const frozen=attempt.current;
  sending.current=true;setState('SENDING');setError('');
  const controller=new AbortController();activeRequest.current=controller;const timer=setTimeout(()=>controller.abort(),15000);
  let result:T|undefined,success=false;
  try{
   if(query){
    const receipt=await api<{request_id:string;status:'SUCCESS'|'FAILED'|'UNKNOWN';response:T|null}>(frozen.resultPath,{signal:controller.signal});
    if(receipt?.request_id!==frozen.requestId)throw new Error('İşlem sonucu kimliği doğrulanamadı.');
    if(receipt.status==='UNKNOWN')throw new Error('Kayıtlı sonuç henüz bulunamadı. Bu, işlemin uygulanmadığını kanıtlamaz.');
    if(receipt.status!=='SUCCESS'||receipt.response===null)throw new Error('İşlem sonucu doğrulanamadı.');
    result=receipt.response;
   }else {rememberPending(frozen.requestId,frozen.resultPath);result=await api<T>(frozen.path,{method:'POST',signal:controller.signal,headers:{'X-V2-Demo-Action':frozen.header},body:frozen.body});}
   if(result===undefined||!frozen.matches(result))throw new Error('Yanıt onaylanan abone işlemiyle eşleşmedi.');
   forgetPending(frozen.requestId);outcome.current='SUCCESS';setState('SUCCESS');success=true;
  }catch(failure){
   // A failed read cannot determine whether the original POST committed.
   const rejected=!query&&failure instanceof ApiError&&[400,401,403,404,409,422].includes(failure.status);
   if(rejected)forgetPending(frozen.requestId);
   outcome.current=rejected?'FAILED':'UNCERTAIN';setState(outcome.current);
   setError(subscriberOperationError(failure));
  }finally{
   clearTimeout(timer);sending.current=false;
   invalidateResources([...subscriberSaveDependencies]);
  }
  if(success&&mounted.current)onSaved(result!);
 }
 return {state,error,send,reset,busy:state==='SENDING',uncertain:state==='UNCERTAIN',failed:state==='FAILED',locked:['SENDING','UNCERTAIN','SUCCESS'].includes(state)};
}
