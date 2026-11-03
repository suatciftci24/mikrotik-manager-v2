#!/usr/bin/env python3
"""Build a local reviewed stream. Never SSH, DB, install, or execute maintenance."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.services.system_settings import Values


def bundle():
    service = (ROOT/'backend/app/services/preferences_repair.py').read_text()
    executor = (ROOT/'deploy/fresh-v2-pilot/preferences-repair-approved.py').read_text()
    ast.parse(service); ast.parse(executor)
    model_hash = hashlib.sha256(json.dumps(Values.model_json_schema(), sort_keys=True).encode()).hexdigest()
    # Installed application is unchanged. Modules exist only in this interpreter.
    code = '''import sys,types,json
sys.path.insert(0,'/srv/mikrotik-manager-v2-fresh-pilot/app/backend')
'''
    for name, source in [('app.services.preferences_repair',service),('reviewed_preferences_executor',executor)]:
        code += f"m=types.ModuleType({name!r});sys.modules[{name!r}]=m\nexec(compile({source!r},'<reviewed-maintenance>','exec'),m.__dict__)\n"
    code += f"m.EXPECTED_VALUES_SCHEMA_SHA256={model_hash!r}\n"
    code += "try:\n sys.exit(m.main())\nexcept Exception:\n print(json.dumps({'status':'BLOCKED','error_code':'MAINTENANCE_GATE_FAILED'}));sys.exit(2)\n"
    ast.parse(code)
    return code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    data=bundle().encode()
    if args.output:
        with args.output.open('xb') as f:
            import os
            os.fchmod(f.fileno(),0o600);f.write(data)
    print(json.dumps({'status':'LOCAL_PREPARED','sha256':hashlib.sha256(data).hexdigest(),
                      'live_executed':False,'separate_approval_required':True}))


if __name__=='__main__':main()
