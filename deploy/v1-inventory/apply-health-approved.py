#!/usr/bin/env python3
"""Previously approved health updater; execution requires separate live approval.

stdin is a JSON payload of base64 files. Importing does not perform IO.
"""
import base64,json,os,pathlib,subprocess,tempfile,shutil,time,urllib.request,urllib.error,http.cookiejar,hashlib
from acceptance import accept_authenticated, AcceptanceError
R=pathlib.Path('/srv/mikrotik-manager-v2-fresh-pilot'); ROLE='v2_fresh_inventory_ro'
def run(a,**k):return subprocess.run(a,check=True,capture_output=True,**k).stdout
def pg(s):return run(['runuser','-u','postgres','--','psql','-XAtq','-v','ON_ERROR_STOP=1','-d','mikrotik_manager'],input=s.encode()).decode().strip()
def main(payload,sql):
 assert os.geteuid()==0 and R.is_dir() and not R.is_symlink()
 unit='mikrotik-v2-fresh-pilot.service'
 assert run(['systemctl','is-active',unit]).strip()==b'active'
 assert pg("SELECT NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls FROM pg_roles WHERE rolname='v2_fresh_inventory_ro'")=='t'
 assert pg("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='v2_fresh_inventory_ro') OR roleid=(SELECT oid FROM pg_roles WHERE rolname='v2_fresh_inventory_ro')")=='0'
 cols=['id','router_id','sampled_at','cpu_load_percent','memory_used_percent','internet_success']
 before={c:pg(f"SELECT has_column_privilege('{ROLE}','public.router_health_samples','{c}','SELECT')")=='t' for c in cols}
 files={p:base64.b64decode(v,validate=True) for p,v in payload.items()}
 assert all(p=='backend/app/adapters/v1_inventory.py' or p.startswith('frontend/dist/') for p in files)
 assert all('..' not in pathlib.Path(p).parts and not pathlib.Path(p).is_absolute() for p in files)
 assert 'frontend/dist/index.html' in files
 config=R/'config/database.env'; handoff=R/'config/v1-inventory.json'
 assert ('V2_V1_INVENTORY_FILE='+str(handoff)) in config.read_text()
 original=json.loads(handoff.read_text()); assert len(original['items'])==9
 backup=pathlib.Path(tempfile.mkdtemp(prefix='health-caf2b4c-before-',dir=R/'backups')); backup.chmod(0o700)
 targets=[R/'app'/p for p in files]+[handoff]
 for i,p in enumerate(targets):
  assert not p.is_symlink()
  if p.exists(): shutil.copy2(p,backup/str(i))
 (backup/'paths.json').write_text(json.dumps([str(p) for p in targets]))
 (backup/'role-before.json').write_text(json.dumps(before))
 changed=False; granted=False
 try:
  pg("""BEGIN; SET LOCAL statement_timeout='5s';
GRANT SELECT(id,router_id,sampled_at,cpu_load_percent,memory_used_percent,internet_success) ON public.router_health_samples TO v2_fresh_inventory_ro;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f') AND
 (has_table_privilege('v2_fresh_inventory_ro',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
 OR EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
 AND (has_column_privilege('v2_fresh_inventory_ro',c.oid,a.attnum,'INSERT,UPDATE,REFERENCES') OR
 (has_column_privilege('v2_fresh_inventory_ro',c.oid,a.attnum,'SELECT') AND NOT
 ((c.relname='routers' AND a.attname IN ('id','name','identity','model','routeros_version')) OR
 (c.relname='router_health_samples' AND a.attname IN ('id','router_id','sampled_at','cpu_load_percent','memory_used_percent','internet_success'))))))))
 THEN RAISE EXCEPTION 'excess read role privilege'; END IF;
 IF has_schema_privilege('v2_fresh_inventory_ro','public','CREATE') THEN RAISE EXCEPTION 'unsafe DDL'; END IF;
END $$; COMMIT;"""); granted=True
  sql=sql.replace('BEGIN READ ONLY;','BEGIN READ ONLY; SET LOCAL ROLE v2_fresh_inventory_ro;',1)
  data=json.loads(pg(sql))
  assert {r['id'] for r in data['items']}=={r['id'] for r in original['items']}
  assert {r['id']:r for r in data['items']}=={r['id']:r for r in original['items']}
  raw=json.dumps(data).encode(); assert len(raw)<1024*1024
  validate="import sys,json,importlib.util; s=importlib.util.spec_from_file_location('inv',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.InventoryFile.model_validate_json(sys.stdin.buffer.read())"
  candidate=backup/'candidate.py'; candidate.write_bytes(files['backend/app/adapters/v1_inventory.py'])
  run([str(R/'venv/bin/python'),'-I','-c',validate,str(candidate)],input=raw)
  changed=True
  for p,b in files.items():
   t=R/'app'/p; t.parent.mkdir(parents=True,exist_ok=True); t.write_bytes(b); t.chmod(0o644)
  temp=handoff.with_suffix('.health-new'); assert not temp.exists()
  temp.write_bytes(raw); os.chown(temp,handoff.stat().st_uid,handoff.stat().st_gid); temp.chmod(0o640); os.replace(temp,handoff)
  run(['systemctl','restart',unit]); url='http://127.0.0.1:18090'
  for _ in range(20):
   try: urllib.request.urlopen(url+'/api/health',timeout=2).close(); break
   except (OSError,urllib.error.URLError):time.sleep(.5)
  client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  try:client.open(url+'/api/v1/v1-inventory',timeout=5); raise AssertionError('anonymous access')
  except urllib.error.HTTPError as e:assert e.code==401
  admin=json.loads((R/'admin-handoff.json').read_text())
  client.open(urllib.request.Request(url+'/api/v1/auth/login',data=json.dumps({'username':admin['username'],'password':admin['password']}).encode(),headers={'Content-Type':'application/json'}),timeout=10).close()
  try:
   receipt=accept_authenticated(client,url,data,files)
   receipt.update(commit='caf2b4c',rollback_directory=str(backup),role=ROLE,device_io=False)
  finally:client.open(urllib.request.Request(url+'/api/v1/auth/logout',data=b''),timeout=5).close()
  (backup/'receipt.json').write_text(json.dumps(receipt)); print(json.dumps(receipt))
 except Exception as e:
  report=e.report if isinstance(e,AcceptanceError) else dict(status='BLOCKED',step='deployment_or_auth',expected='successful operation',actual=type(e).__name__)
  (backup/'acceptance-failure.json').write_text(json.dumps(report))
  if changed:
   for i,p in enumerate(targets):
    saved=backup/str(i)
    if saved.exists():shutil.copy2(saved,p)
    elif p.exists():p.unlink()
   run(['systemctl','restart',unit]); assert run(['systemctl','is-active',unit]).strip()==b'active'
  if granted:
   added=[c for c in cols if not before[c]]
   if added:pg('REVOKE SELECT('+','.join(added)+') ON public.router_health_samples FROM '+ROLE+';')
  report.update(rollback='restored' if changed else 'not needed',backup=str(backup)); print(json.dumps(report))
  raise SystemExit(1)

if __name__ == '__main__':
 import sys
 main(json.load(sys.stdin),(pathlib.Path(__file__).parent/'health-export.sql').read_text())
