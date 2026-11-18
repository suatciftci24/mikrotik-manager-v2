"""Check the current process can create the socket needed by local HTTP tools."""
import errno
import socket
import sys


def socket_blocker():
    """Return safe evidence of socket creation failure without binding any port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
            pass
    except OSError as failure:
        reason = ('LOOPBACK_SOCKET_PERMISSION_DENIED'
                  if failure.errno in (errno.EPERM, errno.EACCES)
                  else 'LOOPBACK_SOCKET_ERROR')
        code = errno.errorcode.get(failure.errno, 'UNKNOWN')
        return f'{reason} syscall=socket family=AF_INET type=SOCK_STREAM errno={code}'
    return None


def main():
    blocker = socket_blocker()
    if blocker:
        print(f'BLOCKED: {blocker}; bu ortamda yerel işlem başlatılmadı.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
