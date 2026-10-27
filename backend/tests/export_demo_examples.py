"""Export actual seed projections for cross-language tests; no DB or socket access."""
import json
from app.services.demo_examples import demo_examples
from app.demo_storage import validated_snapshots
from app.services.demo_reports import router_event_records
from app.services.demo_data import ROUTERS

if __name__ == '__main__':
    samples = validated_snapshots(demo_examples())
    print(json.dumps(dict(samples=samples, events=router_event_records([detail['item'] for detail in samples]).model_dump(mode='json'), routers=ROUTERS)))
