"""Temporary bare Git relay. Never opens a deployment working tree."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

COMMIT = 'b41deae94be7ed2d3790d0a1ecd9cad1c6b06f93'
BASE = '75c27dfd181a677a5d305859393caa1390992065'
BRANCH = 'refs/heads/development/v2.6.2-pppoe'
GITHUB = 'https://github.com/suatciftci24/mikrotik-manager-v2.git'


class Blocked(Exception):
    pass


def need(ok, message):
    if not ok:
        raise Blocked(message)


def git(repo, *args, input=None):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    process = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'push.followTags=false',
                              '-c', 'remote.origin.mirror=false', '-C', str(repo), *args],
                             input=input, capture_output=True, timeout=180, env=env)
    need(process.returncode == 0, 'Git işlemi başarısız: ' + args[0] +
         '; mevcut VDS GitHub kimliği/ağ/yetki durumunu kontrol edin. Hassas hata içeriği gizlendi.')
    return process.stdout


def transfer(pack, expected_hash):
    need(hashlib.sha256(pack).hexdigest() == expected_hash, 'Git aktarım SHA256 uyuşmadı.')
    with tempfile.TemporaryDirectory(prefix='v262-git-transfer-', dir='/tmp') as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        (root/'empty-template').mkdir()
        repo = root/'relay.git'
        git(root, 'init', '--bare', '--template='+str(root/'empty-template'), str(repo))
        git(repo, 'index-pack', '--stdin', '--strict', input=pack)
        need(git(repo, 'rev-parse', COMMIT+'^{commit}').strip().decode() == COMMIT, 'Kaynak commit doğrulanamadı.')
        parents = git(repo, 'rev-list', '--parents', '-n', '1', COMMIT).decode().split()
        need(parents == [COMMIT, BASE], 'Kaynak commit doğrudan onaylı 2.6.1 tabanından gelmiyor.')
        need(json.loads(git(repo, 'show', COMMIT+':release.json'))['version'] == '2.6.2', 'Kaynak sürüm yanlış.')
        git(repo, 'remote', 'add', 'origin', GITHUB)
        # Refuse global URL rewrites to a different destination.
        need(git(repo, 'remote', 'get-url', '--push', 'origin').strip().decode() == GITHUB,
             'GitHub hedef URL yeniden yazılıyor; gönderim durduruldu.')
        before = git(repo, 'ls-remote', 'origin', BRANCH).decode().split()
        need(not before or (len(before)==2 and before[1]==BRANCH), 'Uzak branch yanıtı belirsiz.')
        if before and before[0] != COMMIT:
            git(repo, 'fetch', '--no-tags', '--no-write-fetch-head', 'origin', BRANCH+':refs/relay/previous')
            fetched = git(repo, 'rev-parse', 'refs/relay/previous').strip().decode()
            need(fetched == before[0], 'Uzak dal kontrol sırasında değişti; tekrar gönderim yapılmadı.')
            try:
                git(repo, 'merge-base', '--is-ancestor', fetched, COMMIT)
            except Blocked:
                raise Blocked('Uzak dal hedef commit ile fast-forward değil; dal korunuyor, force yok.') from None
        if not before or before[0] != COMMIT:
            # One explicit non-force refspec; no mirror, branch deletion or tags.
            git(repo, 'push', '--no-verify', '--no-follow-tags', '--porcelain',
                'origin', COMMIT+':'+BRANCH)
        after = git(repo, 'ls-remote', 'origin', BRANCH).decode().split()
        need(after == [COMMIT, BRANCH], 'Gönderim sonrası GitHub SHA eşitliği doğrulanamadı.')
        print('PUSHED v2.6.2 '+COMMIT+' development/v2.6.2-pppoe; canlı VDS ağacı/HEAD değiştirilmedi.', flush=True)
