"""Read-only static acceptance helpers; no deployment or network transport."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import PurePosixPath


class StaticAcceptanceError(ValueError):
    pass


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            src = dict(attrs).get('src')
            if src:
                self.paths.append(src)


def verify_scripts(html, fetch, expected_files):
    """Compare published script bytes with the approved payload, never API literals.

    fetch is caller supplied. This helper neither logs in nor changes remote state.
    Return hashes only; errors contain no served content or application data.
    """
    parser = _Scripts()
    parser.feed(html)
    if not parser.paths or not any(p.startswith('/assets/') for p in parser.paths):
        raise StaticAcceptanceError('MISSING_ENTRY_SCRIPT')
    hashes = {}
    for path in parser.paths:
        if (not path.startswith('/') or path.startswith('//')
                or '..' in PurePosixPath(path).parts or '?' in path or '#' in path):
            raise StaticAcceptanceError('UNSAFE_SCRIPT_PATH')
        key = 'frontend/dist' + path
        if key not in expected_files:
            raise StaticAcceptanceError('UNEXPECTED_SCRIPT')
        expected = sha256(expected_files[key]).hexdigest()
        actual = sha256(fetch(path)).hexdigest()
        if actual != expected:
            raise StaticAcceptanceError(f'SCRIPT_HASH_MISMATCH expected={expected} actual={actual}')
        hashes[path] = actual
    return hashes
