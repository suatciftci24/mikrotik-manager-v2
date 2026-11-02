#!/usr/bin/python3
"""Office WSL: validate SSH policy on VDS in memory; no installation or reload."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    source = (ROOT/'apply-approved-vds.py').read_text()
    match = (ROOT/'sshd-match.conf').read_text()
    remote = ('import sys\nnamespace = {"__name__": "access_check"}\n'
              + 'exec(compile(' + repr(source) + ', "access_check", "exec"), namespace)\n'
              + 'namespace["check_ssh_only"](' + repr(match) + ', sys.argv[1])\n')
    result = subprocess.run([
        'ssh', '-i', '/home/suatpc/.ssh/mikrotik_manager_ed25519',
        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
        '-o', 'ClearAllForwardings=yes', 'mikadmin@185.139.5.51',
        'sudo -n /usr/bin/python3 -I - "$SSH_CONNECTION"',
    ], input=remote, text=True)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
