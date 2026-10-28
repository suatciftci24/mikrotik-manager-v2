"""Own only a newly started local V2 API child; never restart/kill an existing server."""
import argparse
from pathlib import Path
import socket
import signal
import time
import subprocess
import sys
import tempfile
from app.demo_readiness import probe_api, probe_ui, wait_ready
from app.demo_repair import ROOT, RepairBlocked, require


class ManagedAPI:
    label='API'
    port=8000

    def probe(self):return probe_api()

    def command(self):
        return [str(ROOT/'.venv/bin/python'),'-m','uvicorn','app.main:app',
                '--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port','8000']

    def __init__(self):
        self.process=None
        self.log_path=None

    def __enter__(self):
        status=self.probe()
        if status.state=='READY':
            print(f'{self.label} READY: mevcut V2 süreç kullanılacak; yaşam döngüsüne dokunulmaz.',flush=True)
            return self
        require(status.state=='ABSENT',status.detail)
        # Only start when the exact loopback port is free and sockets are permitted.
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
                probe.bind(('127.0.0.1',self.port))
        except OSError:
            raise RepairBlocked(f'Yerel {self.label} portu kullanılamıyor veya sandbox soketi engelliyor; başka servis durdurulmadı.') from None
        runtime=ROOT/'.local/runtime'
        for path in (ROOT/'.local',runtime):
            require(not path.is_symlink(),'V2 log yolu symlink olamaz.')
        runtime.mkdir(parents=True,exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix='accept-'+self.label.lower()+'-',dir=runtime))
        self.log_path=folder/(self.label.lower()+'.log')
        try:
            with self.log_path.open('w') as log:
                self.process=subprocess.Popen(self.command(),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            status=wait_ready(lambda:self.process.poll() is None,probe=self.probe,label=self.label)
            require(status.state=='READY',status.detail)
            print(f'{self.label} READY: bu komutun geçici V2 süreci hazır. Log: '+str(self.log_path),flush=True)
            return self
        except BaseException:
            self.stop()
            print(f'{self.label} başlangıç logu korundu: '+str(self.log_path),file=sys.stderr)
            raise

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait(timeout=3)

    def __exit__(self,*args):
        self.stop()


class ManagedUI(ManagedAPI):
    # Same owner/readiness/cleanup implementation. Vite command lives only in dev.sh.
    label='UI'
    port=5173

    def probe(self):return probe_ui()

    def command(self):
        require((ROOT/'frontend/node_modules/vite/bin/vite.js').is_file(),
                'Vite bağımlılıkları eksik; frontend paketlerini hazırlayın. Servis başlatılmadı.')
        return [str(ROOT/'dev.sh'),'--ui-only']


def require_browser_database():
    from app.core.database import engine
    from app.demo_repair import verify_database, LocalHTTP
    from app.services.demo_subscriptions import DemoStorageUnavailable
    from sqlalchemy.exc import SQLAlchemyError
    try:
        _adapter,rows=verify_database(engine)
        health=LocalHTTP().request('/api/health')
        require(health.get('environment')=='local-demo' and health.get('database_connected') is True
                and health.get('device_adapters_connected') is False,
                'API aynı kalıcı izole V2 DB kaynağını doğrulamıyor; veri değiştirilmedi.')
        print(f'DB READY: izole V2 marker/yetkiler/kaynak doğrulandı; {len(rows)} mevcut kayıt korunuyor.',flush=True)
    except (SQLAlchemyError,DemoStorageUnavailable):
        raise RepairBlocked('DB hazır değil: izole V2 bağlantısı/şema/yetki doğrulanamadı; veri değiştirilmedi. Onarım/seed çalıştırılmadı.') from None
    finally:
        engine.dispose()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Ortak yerel V2 API yöneticisi: mevcut API korunur; gerekirse sadece kendi geçici API sürecini açar ve seçilen kabulü çalıştırır.')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--dev',action='store_true',help='API ve UI ortak yaşam döngüsüyle çalışır; DB veya kabul işlemi başlatmaz.')
    mode.add_argument('--browser',action='store_true',help='Aynı ManagedAPI yaşam döngüsü içinde API ve UI hazır olunca gerçek tarayıcı kabulünü çalıştırır; mevcut servisler korunur.')
    parser.add_argument('--alarm-acceptance',action='store_true',help='Açık yerel alarm kabul bakımı: ek alarm şemasını hazırlar ve yalnız yeni UUID sentetik fixture ekler; ACK kabulünü çalıştırır.')
    parser.add_argument('--user-acceptance',action='store_true',help='Açık yerel kullanıcı şeması hazırlığı; kabul yalnız yeni sentetik kullanıcıları değiştirir.')
    args=parser.parse_args(argv)
    if args.user_acceptance and (not args.browser or args.alarm_acceptance):parser.error('--user-acceptance yalnız --browser ile ve tek başına kullanılabilir')
    if args.alarm_acceptance and not args.browser:parser.error('--alarm-acceptance yalnız --browser ile kullanılabilir')
    def interrupted(_signum,_frame):
        raise KeyboardInterrupt
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:
        with ManagedAPI() as api:
            if args.dev:
                with ManagedUI() as ui:
                    print('Yerel V2 API/UI hazır. Durdur: Ctrl+C',flush=True)
                    while True:
                        for manager in (api,ui):
                            require(manager.process is None or manager.process.poll() is None,
                                    'Bu komutun yerel V2 süreci kapandı; başlangıç logları korundu.')
                        time.sleep(1)

            if args.browser:
                require_browser_database()  # Read-only and before UI/tools or test records.
                worker_env=None
                if args.alarm_acceptance:
                    import os
                    from app.demo_storage import prepare_alarm_acceptance
                    from sqlalchemy.exc import SQLAlchemyError
                    from app.services.demo_subscriptions import DemoStorageUnavailable
                    try:test_id=prepare_alarm_acceptance()
                    except (SQLAlchemyError,DemoStorageUnavailable,ValueError):
                        raise RepairBlocked('Alarm kabul şeması/fixture hazırlığı tamamlanamadı; mevcut kayıtlar sıfırlanmadı.') from None
                    print('Yeni sentetik alarm kabul kaydı korunacak: '+test_id,flush=True)
                    worker_env={**os.environ,'V2_BROWSER_ALARMS_ONLY':'1','V2_BROWSER_ALARMS_ACK':'1','V2_ALARM_TEST_SUBSCRIBER':test_id}
                if args.user_acceptance:
                    import os
                    from app.services.identity import initialize_users
                    from sqlalchemy.exc import SQLAlchemyError
                    from app.services.demo_subscriptions import DemoStorageUnavailable
                    try:initialize_users()
                    except (SQLAlchemyError,DemoStorageUnavailable,ValueError):
                        raise RepairBlocked('Kullanıcı şeması hazırlanamadı; mevcut hesaplar sıfırlanmadı.') from None
                    worker_env={**os.environ,'V2_BROWSER_USERS_ONLY':'1'}
                with ManagedUI():
                    command=[str(ROOT/'browser-accept-demo.sh'),'--with-ready-services']
                    return subprocess.run(command,cwd=ROOT,**({'env':worker_env} if worker_env else {})).returncode
            from app.demo_acceptance import main as accept
            return accept([])
    except KeyboardInterrupt:
        return 130
    except (RepairBlocked,OSError,subprocess.SubprocessError) as failure:
        message=str(failure) if isinstance(failure,RepairBlocked) else type(failure).__name__
        print('HTTP BLOCKED: '+message,file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM,previous)


if __name__=='__main__':raise SystemExit(main())
