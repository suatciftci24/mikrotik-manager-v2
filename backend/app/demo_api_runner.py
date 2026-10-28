"""Own only a newly started local V2 API child; never restart/kill an existing server."""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from app.demo_readiness import probe_api, wait_ready
from app.demo_repair import ROOT, RepairBlocked, require


class ManagedAPI:
    def __init__(self):
        self.process=None
        self.log_path=None

    def __enter__(self):
        status=probe_api()
        if status.state=='READY':
            print('HTTP READY: mevcut V2 API kullanılacak; yaşam döngüsüne dokunulmaz.',flush=True)
            return self
        require(status.state=='ABSENT',status.detail)
        # Only start when the exact loopback port is free and sockets are permitted.
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
                probe.bind(('127.0.0.1',8000))
        except OSError:
            raise RepairBlocked('Yerel API portu kullanılamıyor veya sandbox soketi engelliyor; başka servis durdurulmadı.') from None
        runtime=ROOT/'.local/runtime'
        for path in (ROOT/'.local',runtime):
            require(not path.is_symlink(),'V2 log yolu symlink olamaz.')
        runtime.mkdir(parents=True,exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix='accept-api-',dir=runtime))
        self.log_path=folder/'api.log'
        try:
            with self.log_path.open('w') as log:
                self.process=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','uvicorn','app.main:app',
                    '--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port','8000'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            status=wait_ready(lambda:self.process.poll() is None)
            require(status.state=='READY',status.detail)
            print('HTTP READY: bu komutun geçici V2 API süreci hazır. Log: '+str(self.log_path),flush=True)
            return self
        except BaseException:
            self.stop()
            print('API başlangıç logu korundu: '+str(self.log_path),file=sys.stderr)
            raise

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait(timeout=3)

    def __exit__(self,*args):
        self.stop()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Yerel V2 API hazırsa kullanır; kapalıysa yalnız kendi geçici API sürecini açıp iki yeni sentetik aboneyle kabul çalıştırır. Mevcut süreç/veri değiştirilmez.')
    parser.parse_args(argv)
    try:
        with ManagedAPI():
            from app.demo_acceptance import main as accept
            return accept([])
    except (RepairBlocked,OSError,subprocess.SubprocessError) as failure:
        message=str(failure) if isinstance(failure,RepairBlocked) else type(failure).__name__
        print('HTTP BLOCKED: '+message,file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
