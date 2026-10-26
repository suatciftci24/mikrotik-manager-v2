const API = '/api/v1';

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `API yanıtı: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type Router = {
  id: string; name: string; management_address: string; site: string; model: string;
  routeros_version: string; status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  cpu_percent: number; memory_percent: number; subscriber_count: number; uptime: string;
  last_seen: string; is_demo: true;
};

export type Subscriber = {
  id: string; username: string; customer_name: string; router_name: string; plan: string;
  source: 'LOCAL' | 'RADIUS'; status: 'ACTIVE' | 'PAUSED' | 'PENDING'; monthly_price: number;
  ip_address: string; joined_at: string; last_seen: string | null; is_demo: true;
};

export type DashboardData = {
  summary: { router_count: number; routers_online: number; subscribers_total: number;
    subscribers_online: number; radius_accounts: number; local_accounts: number;
    monthly_revenue: number; attention_count: number };
  traffic: number[];
  activity: { title: string; detail: string; time: string; kind: string }[];
  attention: { router_id: string; message: string; value: number };
  is_demo: true;
};
