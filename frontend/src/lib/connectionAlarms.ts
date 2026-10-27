import type { Router } from './api.ts';
import { buildRouterReport } from './routerReport.ts';

/** Inventory snapshots contain neither internet probes nor WAN transition events. */
export function buildConnectionAlarms(items: Router[]) {
  const report = buildRouterReport(items);
  return {
    is_demo: true as const,
    rows: report.rows.map(row => ({
      id: row.id, name: row.name, site: row.site,
      inventory_status: row.status, source_time: row.source_time,
      internet_status: null, wan: null,
    })),
    internet_outages: null,
    wan_changes: null,
    history: null,
  };
}
