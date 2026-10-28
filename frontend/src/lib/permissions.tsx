import {createContext,useContext} from 'react';
import type {User} from '../components/Sidebar';
export const permissionNames={can_view:'Görebilir',can_manage_pppoe:'PPPoE yönetimi',can_manage_hotspot:'Hotspot yönetimi',can_view_reports:'Raporları görür',can_use_mikajani:'MikAjanı kullanır',can_ack_alarms:'Alarm onaylar'} as const;
export type Permission=keyof typeof permissionNames;
export const PermissionContext=createContext<User|null>(null);
export function can(user:User|null,router:string|undefined|null,permission:Permission){return !!router&&user?.permissions?.[router]?.can_view===true&&user.permissions[router][permission]===true&&(!['can_manage_pppoe','can_manage_hotspot','can_ack_alarms'].includes(permission)||user.role_code==='ADMIN');}
export const useIdentity=()=>useContext(PermissionContext);
