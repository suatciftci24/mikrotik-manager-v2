#!/usr/bin/env python3
"""Approved root-side one-shot inventory handoff; payload supplied through stdin.

No V1 application changes, device IO, passwords or persistent DB login grants.
The NOLOGIN role can be used only by the existing PostgreSQL administrator.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
import http.cookiejar

ROOT = Path('/srv/mikrotik-manager-v2-fresh-pilot')
ROLE = 'v2_fresh_inventory_ro'

def run(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, **kw).stdout

def pg(sql):
    return run(['runuser','-u','postgres','--','psql','-XAtq','-v','ON_ERROR_STOP=1',
                '-d','mikrotik_manager'], input=sql.encode()).decode().strip()

def main(payload, resume_role=False):
    assert os.geteuid() == 0
    assert ROOT.is_dir() and not ROOT.is_symlink()
    assert run(['systemctl','is-active','mikrotik-v2-fresh-pilot.service']).strip() == b'active'
    # Fail before any write if the new role already exists; never adopt privileges.
    assert pg(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}'") == ('1' if resume_role else '0')
    if resume_role:
        assert pg(f"SELECT NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls FROM pg_roles WHERE rolname='{ROLE}'") == 't'
    files = {p:base64.b64decode(b, validate=True) for p,b in payload.items()}
    backend = {'backend/app/adapters/v1_inventory.py','backend/app/api/v1/v1_inventory.py',
               'backend/app/api/v1/app_router.py'}
    assert backend <= files.keys()
    assert all(p in backend or p.startswith('frontend/dist/') for p in files)
    assert all('..' not in Path(p).parts and not Path(p).is_absolute() for p in files)
    assert 'frontend/dist/index.html' in files
    backup = Path(tempfile.mkdtemp(prefix='inventory-before-',dir=ROOT/'backups'))
    config = ROOT/'config/database.env'
    assert b'V2_V1_INVENTORY_FILE' not in config.read_bytes()
    targets = [ROOT/'app'/p for p in files] + [config]
    for i,p in enumerate(targets):
        assert not p.is_symlink()
        if p.exists(): shutil.copy2(p, backup/str(i))
    (backup/'paths.json').write_text(json.dumps([str(p) for p in targets]))
    # Grants and effective privilege checks share a transaction. PUBLIC cannot
    # accidentally expose other V1 tables or non-allowlisted columns to this role.
    create_role = '' if resume_role else f'CREATE ROLE {ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;'
    pg(f"""BEGIN;
{create_role}
ALTER ROLE {ROLE} SET default_transaction_read_only=on;
ALTER ROLE {ROLE} SET statement_timeout='5s';
GRANT CONNECT ON DATABASE mikrotik_manager TO {ROLE};
GRANT USAGE ON SCHEMA public TO {ROLE};
GRANT SELECT(id,name,identity,model,routeros_version) ON public.routers TO {ROLE};
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f') AND
 (has_table_privilege('{ROLE}',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
 OR EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
 AND (has_column_privilege('{ROLE}',c.oid,a.attnum,'INSERT,UPDATE,REFERENCES') OR
 (has_column_privilege('{ROLE}',c.oid,a.attnum,'SELECT') AND NOT
 (c.relname='routers' AND a.attname IN ('id','name','identity','model','routeros_version')))))))
 THEN RAISE EXCEPTION 'excess inventory privileges'; END IF;
 IF has_schema_privilege('{ROLE}','public','CREATE') OR EXISTS
 (SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='{ROLE}'))
 THEN RAISE EXCEPTION 'unsafe role inheritance'; END IF;
END $$;
COMMIT;""")
    snapshot = pg(f"""BEGIN READ ONLY; SET LOCAL ROLE {ROLE}; SET LOCAL statement_timeout='5s';
SELECT json_build_object('source','V1_INVENTORY_EXPORT','items',coalesce(json_agg(t ORDER BY t.id),'[]'::json))
FROM (SELECT id::text,name,identity,model,routeros_version FROM public.routers ORDER BY id LIMIT 2001) t;
ROLLBACK;""")
    # psql command tags are stripped without printing any real inventory fields.
    data = json.loads(snapshot)
    assert len(data['items']) <= 2000
    handoff = ROOT/'config/v1-inventory.json'
    assert not handoff.exists()
    raw = json.dumps(data).encode()
    assert len(raw) <= 1024*1024
    with handoff.open('xb') as f: f.write(raw)
    import pwd
    account = pwd.getpwnam('mikrotik-v2-fresh')
    os.chown(handoff,0,account.pw_gid); handoff.chmod(0o640)
    try:
        for p,content in files.items():
            target = ROOT/'app'/p
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content); target.chmod(0o644)
        with config.open('ab') as f:
            f.write(b'\nV2_V1_INVENTORY_FILE='+str(handoff).encode()+b'\n')
        run(['systemctl','restart','mikrotik-v2-fresh-pilot.service'])
        url = 'http://127.0.0.1:18090'
        # Bounded startup wait, not repeated SSH or repeated test suites.
        for attempt in range(20):
            try:
                urllib.request.urlopen(url+'/api/health',timeout=2).close(); break
            except (OSError,urllib.error.URLError): time.sleep(.5)
        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        try:
            client.open(url+'/api/v1/v1-inventory',timeout=5)
            raise AssertionError('anonymous inventory exposed')
        except urllib.error.HTTPError as e: assert e.code == 401
        admin = json.loads((ROOT/'admin-handoff.json').read_text())
        request = urllib.request.Request(url+'/api/v1/auth/login',data=json.dumps(
            {'username':admin['username'],'password':admin['password']}).encode(),
            headers={'Content-Type':'application/json'})
        client.open(request,timeout=10).close()
        result = json.load(client.open(url+'/api/v1/v1-inventory',timeout=5))
        assert result['is_demo'] is False and result['source']=='V1_INVENTORY_EXPORT'
        assert {r['id'] for r in result['items']} == {r['id'] for r in data['items']}
        assert all(r['status']=='NO_DATA' for r in result['items'])
        client.open(urllib.request.Request(url+'/api/v1/auth/logout',data=b''),timeout=5).close()
        receipt = {'status':'PASS','router_count':len(result['items']),
                   'mode':'one-shot metadata snapshot; no device observations',
                   'role':ROLE,'rollback_directory':str(backup)}
        (backup/'receipt.json').write_text(json.dumps(receipt))
        print(json.dumps(receipt))
    except Exception:
        for i,p in enumerate(targets):
            saved = backup/str(i)
            if saved.exists(): shutil.copy2(saved,p)
            elif p.exists(): p.unlink()
        run(['systemctl','restart','mikrotik-v2-fresh-pilot.service'])
        print('BLOCKED: pilot files/config restored; isolated NOLOGIN role and handoff retained',file=sys.stderr)
        raise

if __name__ == '__main__':
    main(json.loads(sys.stdin.read()))
