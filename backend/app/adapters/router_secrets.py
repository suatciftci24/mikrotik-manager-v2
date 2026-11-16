"""V2-only owner-private credential files. No fallback to pilot/V1/env secrets."""
import json
import os
from pathlib import Path
import stat
from uuid import UUID,uuid4
from app.adapters.cebeci_api_ssl import ApiSslStop

ROOT=Path(__file__).resolve().parents[3]/'.local'/'router-registry'/'secrets'


class RouterSecretVault:
    def __init__(self,root=ROOT):self.root=Path(root)

    def _directory(self,create=False):
        try:
            for index,path in enumerate((self.root.parent.parent,self.root.parent,self.root)):
                if create:
                    try:path.mkdir(mode=0o700)
                    except FileExistsError:pass
                info=path.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&(0o022 if index==0 else 0o077):raise ValueError()
            fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            info=os.fstat(fd)
            if info.st_uid!=os.getuid() or info.st_mode&0o077:
                os.close(fd);raise ValueError()
            return fd
        except (OSError,ValueError):raise ApiSslStop('SECRET_STORAGE_REJECTED') from None

    @staticmethod
    def valid(username,password):
        try:
            if not isinstance(username,str) or not 1<=len(username.encode('utf8'))<=128 or any(ord(c)<32 or ord(c)==127 for c in username):raise ValueError()
            if not isinstance(password,str) or not 1<=len(password.encode('utf8'))<=1024 or any(c in password for c in ('\x00','\r','\n')):raise ValueError()
        except (ValueError,UnicodeError):raise ApiSslStop('CREDENTIAL_FORMAT_REJECTED') from None
        return username,password

    def put(self,username,password):
        self.valid(username,password)
        reference=str(uuid4());directory=self._directory(create=True)
        try:
            fd=os.open(reference,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
            try:
                with os.fdopen(fd,'w',encoding='utf8') as stream:
                    os.fchmod(stream.fileno(),0o600)
                    json.dump({'username':username,'password':password},stream)
                    stream.flush();os.fsync(stream.fileno())
                os.fsync(directory)
            except Exception:
                os.unlink(reference,dir_fd=directory);raise
            return reference
        except (OSError,ValueError):raise ApiSslStop('SECRET_STORAGE_REJECTED') from None
        finally:os.close(directory)

    def read(self,reference):
        directory=self._directory()
        try:
            if str(UUID(reference))!=reference:raise ValueError()
            fd=os.open(reference,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory)
            with os.fdopen(fd,'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1 or info.st_size>8192:raise ValueError()
                data=stream.read(8193)
            payload=json.loads(data)
            if set(payload)!= {'username','password'}:raise ValueError()
            return self.valid(payload['username'],payload['password'])
        except (OSError,ValueError,TypeError,KeyError):raise ApiSslStop('SECRET_STORAGE_REJECTED') from None
        finally:os.close(directory)

    def discard(self,reference):
        directory=self._directory()
        try:
            if str(UUID(reference))!=reference:raise ValueError()
            # Only an exact random file inside our private directory; never follow links.
            os.unlink(reference,dir_fd=directory)
            os.fsync(directory)
        except FileNotFoundError:pass
        except (OSError,ValueError,TypeError):raise ApiSslStop('SECRET_STORAGE_REJECTED') from None
        finally:os.close(directory)
