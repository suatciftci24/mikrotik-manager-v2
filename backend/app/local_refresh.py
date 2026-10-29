"""Explicit local dev refresh. Verify listening socket + repo/UID/argv before signaling."""
import os
from pathlib import Path
import select
import signal
from app.demo_repair import ROOT,RepairBlocked,require,socket_permission
from app.local_ports import api_port,ui_port


def listener_inodes(port,proc=Path('/proc')):
    result=set()
    for filename in ('tcp','tcp6'):
        file=proc/'net'/filename
        if filename=='tcp6' and not file.exists():continue
        for line in file.read_text().splitlines()[1:]:
            fields=line.split()
            address,raw_port=fields[1].split(':')
            if fields[3]!='0A' or int(raw_port,16)!=port:continue
            require(filename=='tcp' and address=='0100007F',f'{port} üzerinde loopback dışı dinleyici var; hiçbir süreç durdurulmadı.')
            result.add(fields[9])
    return result


def identity(pid,label,port,proc=Path('/proc')):
    path=proc/str(pid)
    require(path.stat().st_uid==os.getuid(),'Süreç başka kullanıcıya ait; durdurulmadı.')
    cwd=(path/'cwd').resolve(strict=True)
    argv=(path/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
    start=(path/'stat').read_text().rsplit(')',1)[1].split()[19]
    def option(name,value):return name in argv and argv.index(name)+1<len(argv) and argv[argv.index(name)+1]==value
    if label=='API':
        valid=(cwd==ROOT and Path(argv[0]).absolute()==ROOT/'.venv/bin/python'
               and argv[1:4]==['-m','uvicorn','app.main:app'] and option('--app-dir',str(ROOT/'backend'))
               and option('--host','127.0.0.1') and option('--port',str(port)))
    else:
        entry=Path(argv[1]) if len(argv)>1 else Path('/')
        if not entry.is_absolute():entry=cwd/entry
        valid=(cwd==ROOT/'frontend' and entry.resolve()==ROOT/'frontend/node_modules/vite/bin/vite.js'
               and Path(argv[0]).name in ('node','nodejs') and option('--host','127.0.0.1'))
    require(valid,f'{label} portundaki süreç bu projenin bilinen geliştirme komutuyla eşleşmiyor; hiçbir süreç durdurulmadı.')
    return (tuple(argv),str(cwd),start)


def owner(inodes,proc=Path('/proc')):
    owners=set()
    for path in proc.iterdir():
        if not path.name.isdecimal():continue
        try:
            for fd in (path/'fd').iterdir():
                try:target=os.readlink(fd)
                except OSError:continue
                if target.startswith('socket:[') and target[8:-1] in inodes:owners.add(int(path.name))
        except (PermissionError,FileNotFoundError,ProcessLookupError):continue
    require(len(owners)==1,'Dinleyicinin tek proje sahibi doğrulanamadı; hiçbir süreç durdurulmadı.')
    return owners.pop()


def refresh():
    socket_permission()  # No process inspection/signals when sandbox denies sockets.
    require(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'Güvenli pidfd desteği yok; süreçlere dokunulmadı.')
    targets=[]
    try:
        # Validate/open stable handles for both ports before touching either process.
        for label,port in [('UI',ui_port()),('API',api_port())]:
            inodes=listener_inodes(port)
            if not inodes:continue
            pid=owner(inodes);before=identity(pid,label,port)
            handle=os.pidfd_open(pid)
            try:
                require(identity(pid,label,port)==before,'Süreç kimliği değişti; duruldu.')
            except BaseException:os.close(handle);raise
            targets.append((label,handle))
        for label,handle in targets:
            try:signal.pidfd_send_signal(handle,signal.SIGTERM)
            except ProcessLookupError:pass
            require(bool(select.select([handle],[],[],8)[0]),f'{label} süreci kapanmadı; zorla sonlandırılmadı.')
        print('V2 proje süreçleri güvenle kapatıldı; DB/veri/başka servis değiştirilmedi.')
    finally:
        for _,handle in targets:os.close(handle)


def main():
    try:refresh();return 0
    except (RepairBlocked,OSError,ValueError) as error:
        print('REFRESH BLOCKED: '+(str(error) if isinstance(error,RepairBlocked) else type(error).__name__))
        return 1
if __name__=='__main__':raise SystemExit(main())
