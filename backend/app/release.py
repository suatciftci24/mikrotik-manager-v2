"""Release identity captured once at process startup; no network or database IO."""
import json
from pathlib import Path
import re

VERSION = json.loads((Path(__file__).resolve().parents[2] / 'release.json').read_text())['version']
if not isinstance(VERSION, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', VERSION):
    raise ValueError('release.json: geçerli MAJOR.MINOR.PATCH gerekli')
