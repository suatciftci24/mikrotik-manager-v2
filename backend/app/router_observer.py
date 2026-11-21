"""A standalone poller instance for one explicitly authorized registry router."""
import argparse
from datetime import datetime, timezone
from functools import partial
import os
from pathlib import Path
import signal
from threading import Event

from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.router_api_ssl import RouterApiSslClient
from app.adapters.router_secrets import RouterSecretVault
from app.schemas.device_inventory import RouterObservation
from app.services.device_inventory import sample_device
from app.services.device_poller import poll
from app.services.router_observation_grants import PREFIX, RUN, Scope, approval, read_document

VAULT_ROOT = Path('/var/lib/mikrotik-v2-observers')


def observer_vault(router_id):
    return RouterSecretVault(VAULT_ROOT / router_id / 'router-registry' / 'secrets')


def make_sampler(document, vault, client):
    grant = document.grant
    target = document.target()
    policy = Scope(grant.management_address, grant.source_ip, grant.port).policy()

    router_id = 'device-' + grant.router_id

    def sample(*, previous):
        approval(document)
        try:
            credentials = vault.read(str(grant.credential_ref))
            if credentials[0] != grant.read_only_username:
                raise ApiSslStop('OBSERVATION_CREDENTIAL_SCOPE_REJECTED')
        except ApiSslStop:
            return RouterObservation(id=router_id, observed_at=datetime.now(timezone.utc),
                connection='UNKNOWN', error='AUTHORIZATION',
                last_success_at=previous.last_success_at if previous else None)
        approval(document)
        return sample_device(client, target, credentials, policy, router_id=router_id,
                             wan_interface=grant.wan_interface, previous=previous)
    return sample


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('router_id')
    args = parser.parse_args()
    try:
        if os.geteuid() == 0 or os.environ.get('V2_DEPLOYMENT_PROFILE'):
            raise ValueError('OBSERVATION_RUNTIME_REJECTED')
        document = read_document(args.router_id)
        stop = Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        authorize = partial(approval, document)
        client = RouterApiSslClient(authorize_observation=authorize)
        poll(make_sampler(document, observer_vault(args.router_id), client),
             RUN / (PREFIX + args.router_id), stop, authorize_grant=authorize)
    except (OSError, ValueError, ApiSslStop):
        parser.exit(1, 'ROUTER_OBSERVER_STOPPED\n')


if __name__ == '__main__':
    main()
