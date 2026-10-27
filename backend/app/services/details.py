"""Read-only projections of the existing synthetic inventory. No adapter calls."""
from app.services.demo_data import ROUTERS, SUBSCRIBERS


def router_detail(router_id: str):
    item = next((row for row in ROUTERS if row['id'] == router_id), None)
    if item is None:
        return None
    # The legacy fixture only carries router_name; do not infer live sessions.
    assigned = [row for row in SUBSCRIBERS if row['router_name'] == item['name']]
    return {'item': item, 'assigned_subscribers': assigned, 'is_demo': True}


def subscriber_detail(subscriber_id: str):
    item = next((row for row in SUBSCRIBERS if row['id'] == subscriber_id), None)
    return {'item': item, 'is_demo': True} if item else None
