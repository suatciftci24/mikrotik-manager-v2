#!/usr/bin/env python3
"""Build an offline, self-contained VDS installer from a clean committed tree."""
import base64
import gzip
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = '''#!/usr/bin/env bash
set +x
set -euo pipefail
if [[ $EUID -ne 0 ]]; then exec sudo bash "$0"; fi
python3 - "$0" <<'V2_PYTHON'
import base64,gzip,io,os,pathlib,pwd,subprocess,sys,tarfile,tempfile
stage=None
try:
 operator=pwd.getpwnam('mikadmin')
 payload=pathlib.Path(sys.argv[1]).read_bytes().split(b'\\n# V2_SOURCE_PAYLOAD\\n',1)[1]
 archive=gzip.decompress(base64.b64decode(payload))
 stage=pathlib.Path(tempfile.mkdtemp(prefix='v2-complete.',dir='/home/mikadmin'))
 os.chown(stage,operator.pw_uid,operator.pw_gid)
 def write(name,value):
  fd=os.open(stage/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as stream:
   stream.write(value);os.fchown(stream.fileno(),operator.pw_uid,operator.pw_gid)
 write('app.tar',archive)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
  for name in ('complete-vds.py','native-admin.py'):
   member=tar.getmember('deploy/cebeci-v2-pilot/'+name)
   if not member.isfile():raise RuntimeError('source rejected')
   write(name,tar.extractfile(member).read())
 result=subprocess.run(['python3',str(stage/'native-admin.py'),str(stage)])
 sys.exit(result.returncode)
except Exception:
 print('BLOCKED: V2_NATIVE_INSTALLER_PREFLIGHT',file=sys.stderr);sys.exit(1)
V2_PYTHON
exit $?
# V2_SOURCE_PAYLOAD
'''


def main():
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip():
        raise RuntimeError('clean committed tree required')
    archive = subprocess.check_output(['git', 'archive', '--format=tar', 'HEAD'], cwd=ROOT)
    output = ROOT / '.local/mikrotik-v2-native-admin.run'
    output.parent.mkdir(exist_ok=True)
    with output.open('x') as stream:
        stream.write(LAUNCHER)
        stream.write(base64.b64encode(gzip.compress(archive, mtime=0)).decode() + '\n')
    output.chmod(0o700)
    print(str(output))


if __name__ == '__main__':
    main()
