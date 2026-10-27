"""Read-only projections of the existing synthetic inventory. No adapter calls."""
from app.services.demo_data import ROUTERS
from app.services import demo_subscriptions


def router_detail(router_id: str):
    item = next((row for row in ROUTERS if row['id'] == router_id), None)
    if item is None:
        return None
    # The legacy fixture only carries router_name; do not infer live sessions.
    assigned = [row for row in demo_subscriptions.store.list_items() if (row.get('router_id') == item['id'] if row.get('router_id') else row['router_name'] == item['name'])]
    # Snapshot metadata lives in the same persisted subscriber payload as events/measurements.
    reports = [row['demo_report'] for row in assigned if row.get('demo_report') and row['demo_report'].get('wan_snapshot')]
    if reports:
        from app.schemas.demo_reports import DemoReport
        reports = [DemoReport.model_validate(report) for report in reports]
        latest = max(reports, key=lambda report: report.recorded_at)
        item = {**item, 'wan_snapshot': latest.wan_snapshot.model_dump(mode='json')}
    return {'item': item, 'assigned_subscribers': assigned, 'is_demo': True}


def subscriber_detail(subscriber_id: str):
    return demo_subscriptions.store.detail(subscriber_id)
