import type { Router, Subscriber } from './api.ts';

/** Prefer saved identity; legacy name matching never overrides an explicit router ID. */
export function assignedToRouter(subscriber: Subscriber, router: Router): boolean {
  return subscriber.router_id ? subscriber.router_id===router.id : subscriber.router_name===router.name;
}
