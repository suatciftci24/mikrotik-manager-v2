"""Explicit foreground entry for the independent observer. No application startup hook."""
import argparse
import signal
import sys
from threading import Event

from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.cebeci_observer import ROOT, authorize, make_sampler
from app.services.device_poller import poll


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('preflight', 'run'))
    args = parser.parse_args()
    try:
        if args.action == 'preflight':
            authorize()
            print('V2614_CEBECI_OBSERVER_APPROVAL_OK')
            return 0
        sample = make_sampler()
        stop = Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        poll(sample, ROOT, stop)
        return 0
    except ApiSslStop as error:
        code = str(error)
        print(code if code.startswith('V2614_CEBECI_OBSERVER_') else 'V2614_CEBECI_OBSERVER_MATERIAL_REJECTED',
              file=sys.stderr)
    except (OSError, ValueError):
        print('V2614_CEBECI_OBSERVER_LOCAL_IO_REJECTED', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
