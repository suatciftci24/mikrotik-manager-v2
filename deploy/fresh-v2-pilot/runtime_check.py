"""API service precondition: exact closed profile and completed installation, no migration."""
import json
import ipaddress
import stat
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'backend'))


def main():
    try:
        from app.core.fresh_pilot import validate, ROOT
        validate(root=HERE.parents[1])
        import manage
        manifest_bytes, manifest, _ = manage.check_sources()
        from app.core.database import engine
        with engine.begin() as c:
            manage.execute(c, 'SET TRANSACTION READ ONLY')
            # Ledger intentionally inaccessible to API. Owner's acceptance receipt is
            # root-owned, not writable by either API or DB service accounts.
            path = ROOT/'accepted.json'
            info = path.lstat()
            manage.need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022, 'ACCEPTANCE_OWNER_REJECTED')
            receipt = json.loads(path.read_text())
            manage.need(receipt == {'profile':'fresh-v2-pilot', 'manifest_sha256':manage.digest(manifest_bytes)}, 'ACCEPTANCE_REQUIRED')
            row = tuple(manage.execute(c, 'SELECT current_database(),current_user,inet_server_port(),inet_server_addr()::text').one())
            manage.need(row[:3] == (manage.DATABASE,manage.APP,55442) and str(ipaddress.ip_interface(row[3]).ip) == '127.0.0.1', 'API_DATABASE_IDENTITY_REJECTED')
            manage.verify_schema(c)
            from app.services.identity_setup import inspect_setup
            manage.need(inspect_setup(c).closed, 'ADMIN_SEAL_REQUIRED')
        return 0
    except Exception:
        print('BLOCKED: FRESH_PILOT_API_ACCEPTANCE_REQUIRED', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
