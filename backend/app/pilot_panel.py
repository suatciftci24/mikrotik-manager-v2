"""Same-origin static V2 panel + existing API factory. No server/device/DB startup.

For the separately approved VDS pilot service; never installs or starts services.
"""
from pathlib import Path
from fastapi.staticfiles import StaticFiles

ROOT=Path(__file__).resolve().parents[2]


def mount_panel(application,root=ROOT):
    root=Path(root)
    directory=root/'frontend'/'dist'
    index=directory/'index.html'
    if (not directory.is_dir() or directory.is_symlink() or (root/'frontend').is_symlink()
            or not index.is_file() or index.is_symlink()
            or directory.resolve()!=root.resolve()/'frontend'/'dist'):
        raise RuntimeError('V2_PILOT_FRONTEND_BUILD_REQUIRED')
    if any(getattr(route,'path',None) in ('','/') for route in application.routes):
        raise RuntimeError('V2_PILOT_ROOT_ROUTE_CONFLICT')
    # Existing /api routes retain precedence. StaticFiles rejects escaping symlinks/traversal.
    application.mount('/',StaticFiles(directory=directory,html=True,follow_symlink=False),name='v2-pilot-panel')
    return application


def create_app():
    # Importing this factory does not load a backend, open sockets or read credentials.
    from app.main import app
    return mount_panel(app)
