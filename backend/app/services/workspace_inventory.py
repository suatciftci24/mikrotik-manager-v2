"""Read-only V26 router choices; keep identity grants and admin policy unchanged."""
import os
from app.services.demo_data import ROUTERS


def persistent_inventory():
    return os.environ.get('V2_DEPLOYMENT_PROFILE') == 'v26-isolated-acceptance'


def router_choices():
    if not persistent_inventory():
        return [dict(id=row['id'], name=row['name']) for row in ROUTERS]
    from app.services.router_workspace import workspace
    rows = []
    page = 1
    while True:
        result = workspace.list('DEMO_ROUTER', '', page, 100)
        rows.extend(dict(id=row['id'], name=row['fields']['name']) for row in result['items'])
        if page * 100 >= result['total']:
            return rows
        page += 1


def permission_router_ids():
    # Existing legacy grants must survive editing; new choices must be stored IDs.
    return {row['id'] for row in ROUTERS} | {row['id'] for row in router_choices()}
