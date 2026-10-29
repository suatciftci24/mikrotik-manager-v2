"""Immutable source identity captured at process import, not recalculated on HTTP calls."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[2]
REPO_ID=hashlib.sha256(str(ROOT).encode()).hexdigest()
_digest=hashlib.sha256()
for _path in sorted((ROOT/'backend/app').rglob('*.py')):
    _digest.update(str(_path.relative_to(ROOT)).encode());_digest.update(b'\0');_digest.update(_path.read_bytes());_digest.update(b'\0')
BUILD_ID=_digest.hexdigest()

def current_contract(payload):
    from app.local_ports import api_port
    return payload.get('api_port')==api_port() and payload.get('repo_id')==REPO_ID and payload.get('build_id')==BUILD_ID and payload.get('router_workspace_version')==1
