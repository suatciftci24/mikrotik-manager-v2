import {api} from './api.ts';
import {allPages} from './workspaceDashboard.ts';
export type PackageFields={name:string;download_mbps:number;upload_mbps:number;router_profile:string|null;monthly_price:string|null;duration_days:number;active:boolean};
export type PackageRecord={id:string;revision:number;fields:PackageFields;is_demo:true};
export async function loadPackageChoices(_path:string,init?:RequestInit){return {items:await allPages<PackageRecord>('/packages',init)};}
export function packageEnd(start:string,days:number){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(start)||!Number.isInteger(days)||days<1||days>3660)return '';
 const day=new Date(start+'T00:00:00Z');if(!Number.isFinite(day.getTime())||day.toISOString().slice(0,10)!==start)return '';day.setUTCDate(day.getUTCDate()+days-1);
 const end=Number.isFinite(day.getTime())?day.toISOString().slice(0,10):'';
 return /^\d{4}-\d{2}-\d{2}$/.test(end)?end:'';
}
export const packagePrice=(value:string|null)=>value===null?'Ücret belirtilmedi':new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY'}).format(Number(value));
