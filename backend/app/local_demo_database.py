"""Normal dev startup: resume an existing repo-owned demo cluster; never provision it."""
import socket
import subprocess
import sys
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import engine
from app.demo_repair import ROOT, RepairBlocked, preflight, require, verify_database
from app.services.demo_subscriptions import DemoStorageUnavailable

PG_CTL='/usr/lib/postgresql/16/bin/pg_ctl'


def ensure_database(destination=engine,root=ROOT):
    preflight(destination,root)
    cluster=root/'.local/postgres-v2-demo'
    version=cluster/'PG_VERSION'
    require(version.is_file() and not version.is_symlink() and version.read_text().strip()=='16',
            'Mevcut V2 PostgreSQL 16 kümesi yok veya doğrulanamadı; otomatik kurulum/seed yapılmadı.')
    socket_dir=root/'.local/postgres-v2-socket'
    require(socket_dir.is_dir(),'Mevcut V2 socket dizini yok; otomatik kurulum yapılmadı.')
    status=subprocess.run([PG_CTL,'-D',str(cluster),'status'],capture_output=True,timeout=5)
    require(status.returncode in (0,3),'V2 PostgreSQL durum kontrolü başarısız; küme değiştirilmedi.')
    if status.returncode==3:
        # An unrelated listener must never be adopted, stopped or reconfigured.
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1',55432))
        subprocess.run([PG_CTL,'-D',str(cluster),'-l',str(root/'.local/postgres-v2.log'),
                        '-o',f'-h 127.0.0.1 -p 55432 -k {socket_dir}',
                        '-w','-t','15','start'],check=True,timeout=20)
    # Same storage marker, data directory and privileges as existing read-only repair.
    # A missing DB/schema or bad credentials is an error, never permission to create it.
    _adapter,rows=verify_database(destination)
    print(f'V2 DB READY: mevcut yerel demo kümesi/şeması doğrulandı; {len(rows)} abone korunuyor.',flush=True)


def main():
    try:
        ensure_database()
        return 0
    except (RepairBlocked,DemoStorageUnavailable,SQLAlchemyError,OSError,subprocess.SubprocessError) as failure:
        detail=str(failure) if isinstance(failure,RepairBlocked) else type(failure).__name__
        print('V2 DB BLOCKED: '+detail+'; veri/şema/rol/parola sıfırlanmadı. API/UI başlatılmadı.',file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__=='__main__':raise SystemExit(main())
