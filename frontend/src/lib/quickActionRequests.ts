/** In-memory identity markers for QuickActions requests awaiting receipt checks. */
export type QuickActionRequest={requestId:string;itemId:string;action:string};
const pending=new Map<string,QuickActionRequest>();
export function rememberQuickActionRequest(request:QuickActionRequest){pending.set(request.requestId,request);}
export function forgetQuickActionRequest(requestId:string){pending.delete(requestId);}
export function pendingQuickActionRequests(){return [...pending.values()];}
