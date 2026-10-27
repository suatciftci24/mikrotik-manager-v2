const API = '/api/v1';

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `API yanıtı: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type Router = {
  wan_snapshot?: {interface:string;ip:string;gateway:string;default_route:string;is_demo:true}|null;
  id: string; name: string; management_address: string; site: string; model: string;
  routeros_version: string; status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  cpu_percent: number; memory_percent: number; subscriber_count: number; uptime: string;
  last_seen: string; is_demo: true;
};

export type DemoSession = {id:string;started_at:string|null;ended_at:string|null;state:'ACTIVE'|'CLOSED'|'UNKNOWN';is_demo:true};
export type DemoTraffic = {id:string;measured_at:string;download_bytes:number|null;upload_bytes:number|null;is_demo:true};
export type DemoReport = {subscriber_id:string;router_id:string;recorded_at:string;sessions:DemoSession[];traffic:DemoTraffic[];is_demo:true};
export type Subscriber = {
  demo_report?: DemoReport | null;
  access_type?: 'PPPOE' | null; router_id?: string | null;
  id: string; username: string; customer_name: string; router_name: string; plan: string;
  source: 'LOCAL' | 'RADIUS' | null; status: 'ACTIVE' | 'PAUSED' | 'PENDING'; monthly_price: number;
  ip_address: string; joined_at: string; expires_on: string | null; revision: number; last_seen: string | null; is_demo: true;
};

export type DashboardData = {
  summary: { router_count: number; routers_online: number; subscribers_total: number;
    subscribers_online: number | null; radius_accounts: number; local_accounts: number;
    monthly_revenue: number; attention_count: number };
  traffic: number[] | null;
  activity: { title: string; detail: string; time: string; kind: string }[] | null;
  attention: { router_id: string; message: string; value: number } | null;
  is_demo: true;
};

export type SubscriberHistoryEvent = {
  id: string; occurred_at: string; previous_expires_on?: string | null; expires_on?: string | null;
  previous_values?: Record<string, string | number | null>; new_values?: Record<string, string | number | null>;
  actor_id: string;
  operation: 'RENEWAL' | 'DATE_EDIT' | 'CREATE' | 'PLAN_CHANGE' | 'STATUS_CHANGE'; source: 'LOCAL' | 'RADIUS'; is_demo: true;
};
export type SubscriberDetailData = {item: Subscriber; history: SubscriberHistoryEvent[]; is_demo: true; persistence: 'process-memory' | 'local-postgresql-demo'};

export type DemoOptions = {
  plans: {name: string; monthly_price: number}[]; routers: {id: string; name: string}[];
  is_demo: true; persistence: 'local-postgresql-demo';
};
