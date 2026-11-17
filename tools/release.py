"""Check or bump local stable release metadata. Never commits, tags or deploys."""
import argparse
import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    version = json.loads((root / 'release.json').read_text())['version']
    if not isinstance(version, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Geçerli MAJOR.MINOR.PATCH gerekli')
    package = json.loads((root / 'frontend/package.json').read_text())
    lock = json.loads((root / 'frontend/package-lock.json').read_text())
    if {package['version'], lock['version'], lock['packages']['']['version']} != {version}:
        raise ValueError('Paket sürümleri release.json ile eşleşmiyor')
    if f'## [{version}] - ' not in (root / 'CHANGELOG.md').read_text():
        raise ValueError('CHANGELOG sürüm kaydı eksik')
    return version


def bump(part, note, root=ROOT):
    current = check(root)
    if not note.strip() or '\n' in note or '\r' in note:
        raise ValueError('Tek satırlık değişiklik açıklaması gerekli')
    numbers = list(map(int, current.split('.')))
    index = ('major', 'minor', 'patch').index(part)
    numbers[index] += 1
    numbers[index + 1:] = [0] * (2 - index)
    version = '.'.join(map(str, numbers))
    path = root / 'CHANGELOG.md'
    history = path.read_text()
    if f'## [{version}] - ' in history:
        raise ValueError('Hedef sürüm geçmişte zaten var')
    (root / 'release.json').write_text(json.dumps({'version': version}, indent=2) + '\n')
    for name in ('package.json', 'package-lock.json'):
        path = root / 'frontend' / name
        data = json.loads(path.read_text())
        data['version'] = version
        if name == 'package-lock.json':
            data['packages']['']['version'] = version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    entry = f'## [{version}] - {datetime.date.today().isoformat()}\n\n- {note.strip()}\n\n'
    (root / 'CHANGELOG.md').write_text(history.replace('\n## [', '\n' + entry + '## [', 1))
    return check(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'major', 'minor', 'patch'))
    parser.add_argument('--note')
    args = parser.parse_args()
    if args.action != 'check' and not args.note:
        parser.error('--note gerekli')
    print(check() if args.action == 'check' else bump(args.action, args.note))
