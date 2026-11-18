"""Run in normal office WSL. Transfer only the pinned Git graph through the VDS."""
import argparse
import hashlib
from pathlib import Path
import shlex
import subprocess
import sys
from v262_git_relay_remote import COMMIT, BASE, Blocked

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-pinned-relay', action='store_true',
                        help='explicitly request the historical pinned relay to GitHub')
    if not parser.parse_args(argv).execute_pinned_relay:
        raise Blocked('Tarihsel relay için --execute-pinned-relay açıkça gerekli; aktarım başlamadı.')
    preflight = subprocess.run(['/bin/bash', str(ROOT/'tools/check-git-transfer.sh')],
                               stdout=subprocess.DEVNULL)
    if preflight.returncode:
        raise Blocked('Yerel Git aktarım hedefi doğrulanamadı.')
    def git(*args, **kwargs):
        return subprocess.check_output(['git','-C',str(ROOT),*args], **kwargs)
    if git('branch','--show-current').strip() != b'development/v2.6.2-pppoe' or git('status','--porcelain').strip():
        raise Blocked('Yanlış dal/kirli yerel ağaç; aktarım başlamadı.')
    if git('rev-parse','b41deae^{commit}').strip().decode() != COMMIT:
        raise Blocked('Kaynak commit uyuşmuyor.')
    if git('rev-list','--parents','-n','1',COMMIT).decode().split() != [COMMIT, BASE]:
        raise Blocked('Kaynak tabanı uyuşmuyor.')
    # Includes only ancestors of b41deae, never later workflow/diagnostic commits.
    pack = git('pack-objects','--stdout','--revs', input=(COMMIT+'\n').encode())
    if len(pack)>256*1024*1024:
        raise Blocked('Aktarım boyutu güvenli sınırı aşıyor; veri gönderilmedi.')
    digest = hashlib.sha256(pack).hexdigest()
    source = (ROOT/'tools/v262_git_relay_remote.py').read_text()
    source += "\nimport sys\ntry:\n transfer(sys.stdin.buffer.read(256*1024*1024+1), '"+digest+"')\nexcept BaseException as error:\n print('BLOCKED: '+(str(error) if isinstance(error,Blocked) else type(error).__name__),flush=True)\n raise SystemExit(1)\n"
    command = 'python3 -I -B -c '+shlex.quote(source)
    print('SOURCE VERIFIED: '+COMMIT+'; yalnız geçici bare Git aktarımı.', flush=True)
    result = subprocess.run(['ssh','-T','-i',str(Path.home()/'.ssh/mikrotik_manager_ed25519'),
                             '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                             '-o','ConnectTimeout=10','mikadmin@185.139.5.51',command],input=pack)
    if result.returncode:
        raise Blocked('WSL→VDS→GitHub aktarımı tamamlanamadı; otomatik tekrar/force yok.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('BLOCKED: '+(str(error) if isinstance(error,Blocked) else type(error).__name__),file=sys.stderr)
        sys.exit(1)
