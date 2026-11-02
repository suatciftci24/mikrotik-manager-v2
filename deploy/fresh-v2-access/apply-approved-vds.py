#!/usr/bin/python3
"""Executed only over approved administrator SSH, with reviewed public package in PAYLOAD."""
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys

USER = 'v2-fresh-ops'
WRAPPER = Path('/usr/local/sbin/mikrotik-v2-fresh-ssh')
POLICY = Path('/etc/sudoers.d/mikrotik-v2-fresh-ops')
HOME = Path('/home/v2-fresh-ops')
KEYDIR = Path('/etc/ssh/authorized_keys')
KEY = KEYDIR / USER
CONFIG = Path('/etc/ssh/sshd_config')
BEFORE = Path('/etc/ssh/sshd_config.v2-fresh-access-before')
CANDIDATE = Path('/etc/ssh/sshd_config.v2-fresh-access-candidate')
CREATED_KEY = False


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def run(argv, accepted=(0,)):
    result = subprocess.run(argv, env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C'},
                            capture_output=True, text=True)
    need(result.returncode in accepted, 'COMMAND_FAILED:' + argv[0])
    return result.stdout


def safe(path):
    for item in (path, *path.parents):
        s = item.lstat()
        need(not stat.S_ISLNK(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             'UNSAFE_PATH:' + str(item))


def exclusive(path, content, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'w') as output:
        output.write(content)
    os.chmod(path, mode)


def effective(config, user, address):
    return run(['/usr/sbin/sshd','-T','-f',str(config),'-C',
                f'user={user},host=office,addr={address},laddr=185.139.5.51,lport=22'])


def apply(payload, connection):
    global CREATED_KEY
    need(os.geteuid() == 0, 'ROOT_REQUIRED')
    need(set(payload) == {'wrapper','policy','match','public_key'}, 'PAYLOAD_INVALID')
    key = payload['public_key'].strip().split()
    need(len(key) >= 2 and key[0] == 'ssh-ed25519' and '\n' not in payload['public_key'].strip(),
         'PUBLIC_KEY_INVALID')
    for name in (USER,):
        try:
            pwd.getpwnam(name)
        except KeyError:
            pass
        else:
            raise RuntimeError('ACCOUNT_EXISTS')
        try:
            grp.getgrnam(name)
        except KeyError:
            pass
        else:
            raise RuntimeError('GROUP_EXISTS')
    for path in (WRAPPER, POLICY, HOME, KEY, BEFORE, CANDIDATE):
        need(not os.path.lexists(path), 'TARGET_EXISTS:' + str(path))
    need(not os.path.lexists('/srv/mikrotik-manager-v2-fresh-pilot'), 'PILOT_ROOT_EXISTS_REVIEW_REQUIRED')
    for unit in ('mikrotik-v2-fresh-pilot.service','mikrotik-v2-fresh-pilot-db.service'):
        for directory in ('/etc/systemd/system','/run/systemd/system','/usr/lib/systemd/system','/lib/systemd/system'):
            need(not os.path.lexists(Path(directory)/unit), 'UNIT_EXISTS_REVIEW_REQUIRED')
    for path in (WRAPPER.parent, POLICY.parent, HOME.parent, CONFIG):
        safe(path)
    if KEYDIR.exists():
        safe(KEYDIR)
    else:
        need(not os.path.lexists(KEYDIR), 'KEYDIR_SYMLINK')
        safe(KEYDIR.parent)
    run(['/usr/sbin/sshd','-t'])
    run(['/usr/sbin/visudo','-c'])
    need(run(['/usr/bin/systemctl','is-active','ssh.service']).strip() == 'active', 'SSH_UNIT_NOT_ACTIVE')
    users = [account.pw_name for account in pwd.getpwall()]
    addresses = sorted(set(['127.0.0.1','::1', connection.split()[0]]))
    before = {(user, address):effective(CONFIG,user,address) for user in users for address in addresses}
    original = CONFIG.read_text()
    candidate = original.rstrip('\n') + '\n\n' + payload['match']
    exclusive(BEFORE, original, 0o600)
    exclusive(CANDIDATE, candidate, 0o600)
    run(['/usr/sbin/sshd','-t','-f',str(CANDIDATE)])
    for (user,address), settings in before.items():
        need(effective(CANDIDATE,user,address) == settings, 'EXISTING_USER_POLICY_CHANGED')
    for address in addresses:
        values = dict(line.split(' ',1) for line in effective(CANDIDATE,USER,address).splitlines())
        for key_name, expected in {
            'forcecommand':str(WRAPPER), 'disableforwarding':'yes', 'permittty':'no',
            'permituserrc':'no','permituserenvironment':'no','passwordauthentication':'no',
            'kbdinteractiveauthentication':'no','authenticationmethods':'publickey',
            'authorizedkeysfile':str(KEY),'pubkeyauthentication':'yes','x11forwarding':'no'
        }.items():
            need(values.get(key_name) == expected, 'EFFECTIVE_SSH_RESTRICTION_FAILED:' + key_name)
    print('PASS: PREFLIGHT; EXISTING_SSH_POLICIES_IDENTICAL', flush=True)
    # New account remains without a usable authorized key until all policy checks pass.
    run(['/usr/sbin/useradd','--user-group','--no-create-home','--home-dir',str(HOME),
         '--shell','/bin/sh','--password','!',USER])
    HOME.mkdir(mode=0o755)
    need(os.getgrouplist(USER,pwd.getpwnam(USER).pw_gid) == [pwd.getpwnam(USER).pw_gid], 'EXTRA_GROUPS')
    exclusive(WRAPPER,payload['wrapper'],0o755)
    exclusive(POLICY,payload['policy'],0o440)
    run(['/usr/sbin/visudo','-c'])
    for denied in (['/bin/sh'],['/usr/bin/id'],['/usr/bin/systemctl','start','ssh.service'],
                   ['/usr/bin/systemctl','daemon-reload'],['/usr/bin/cat','/etc/shadow']):
        r = subprocess.run(['/usr/bin/sudo','-n','-l','-U',USER,*denied],capture_output=True)
        need(r.returncode != 0, 'UNEXPECTED_SUDO_GRANT')
    listing = run(['/usr/bin/sudo','-n','-l','-U',USER])
    need('(ALL)' not in listing and 'NOPASSWD: ALL' not in listing, 'BROAD_SUDO_GRANT')
    need(CONFIG.read_text() == original, 'SSH_CONFIG_CHANGED_CONCURRENTLY')
    with CONFIG.open('a') as output:
        output.write('\n\n' + payload['match'])
    run(['/usr/sbin/sshd','-t'])
    for (user,address), settings in before.items():
        need(effective(CONFIG,user,address) == settings, 'LIVE_EXISTING_POLICY_CHANGED')
    if not KEYDIR.exists():
        KEYDIR.mkdir(mode=0o755)
    exclusive(KEY,'restrict ' + ' '.join(key[:2]) + '\n',0o600)
    CREATED_KEY = True
    safe(KEY)
    run(['/usr/bin/systemctl','reload','ssh.service'])
    print('PASS: ACCESS_INSTALLED; SSH_RELOADED; PILOT_SERVICES_NOT_TOUCHED',flush=True)
    print('PUBLIC_KEY_FINGERPRINT ' + run(['/usr/bin/ssh-keygen','-lf',str(KEY)]).split()[1],flush=True)
    print('EXISTING_SSH_ACCOUNTS_VERIFIED',len(users),'CONTEXTS',len(addresses),flush=True)


if __name__ == '__main__':
    try:
        apply(PAYLOAD, sys.argv[1])
    except Exception as exc:
        # Do not print raw subprocess output or sensitive input. Preserve evidence.
        # If account creation happened, lock access by removing only this new key.
        if CREATED_KEY and KEY.exists() and KEY.is_file() and not KEY.is_symlink():
            KEY.rename(KEY.with_name(USER + '.disabled'))
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print('BLOCKED: ACCESS_APPLY_FAILED; NEW_KEY_DISABLED_IF_CREATED; KEEP_ARTIFACTS; ' + reason,file=sys.stderr)
        sys.exit(2)
