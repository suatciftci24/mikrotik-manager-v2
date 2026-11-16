"""Pin existing V26 mutable files while application code runs from immutable releases."""
import os
from pathlib import Path
import stat

CENTRAL_ROOT=Path('/srv/mikrotik-v26-next/.local')


def state_root(default):
    value=os.environ.get('V2_CENTRAL_STATE_ROOT')
    if value is None:return Path(default)
    path=Path(value)
    if (os.environ.get('V2_DEPLOYMENT_PROFILE')!='v26-isolated-acceptance' or path!=CENTRAL_ROOT
            or path.resolve()!=CENTRAL_ROOT):
        raise RuntimeError('CENTRAL_STATE_ROOT_REJECTED')
    try:info=path.lstat()
    except OSError:raise RuntimeError('CENTRAL_STATE_ROOT_REJECTED') from None
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o022:
        raise RuntimeError('CENTRAL_STATE_ROOT_REJECTED')
    return path
