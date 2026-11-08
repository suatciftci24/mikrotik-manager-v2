import {createContext,useContext} from 'react';
import type {User} from '../components/Sidebar';
export const permissionNames={can_view:'Görebilir',can_manage_pppoe:'PPPoE yönetimi',can_manage_hotspot:'Hotspot yönetimi',can_view_reports:'Raporları görür',can_use_mikajani:'MikAjanı kullanır',can_ack_alarms:'Alarm onaylar'} as const;
export type Permission=keyof typeof permissionNames;
export const PermissionContext=createContext<User|null>(null);
export function can(user:User|null,router:string|undefined|null,permission:Permission){const allowedRole=permission==='can_ack_alarms'?user?.role_code==='ADMIN':['can_manage_pppoe','can_manage_hotspot'].includes(permission)?['ADMIN','OPERATOR'].includes(user?.role_code??''):true;return !!router&&user?.permissions?.[router]?.can_view===true&&user.permissions[router][permission]===true&&allowedRole;}
export const useIdentity=()=>useContext(PermissionContext);
