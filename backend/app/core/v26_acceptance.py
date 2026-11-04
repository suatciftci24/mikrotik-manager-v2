"""Isolated V2.6 acceptance profile.

Local configuration validation only.
Does not connect to a database, router, RADIUS or VDS.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit, unquote

PROFILE = "v26-isolated-acceptance"
PORT = "18996"


def validate(values=None):
    values = dict(os.environ if values is None else values)

    if values.get("V2_DEPLOYMENT_PROFILE") != PROFILE:
        raise RuntimeError("V26_ACCEPTANCE_PROFILE_REJECTED")

    if values.get("V2_API_PORT") != PORT:
        raise RuntimeError("V26_ACCEPTANCE_PORT_REJECTED")

    if values.get("V2_ROUTER_ONBOARDING_ENABLED") != "false":
        raise RuntimeError("V26_ACCEPTANCE_ROUTER_ACCESS_REJECTED")

    if values.get("V2_CEBECI_API_SSL_ENABLED") != "false":
        raise RuntimeError("V26_ACCEPTANCE_ROUTER_ACCESS_REJECTED")

    if values.get("V2_ROUTER_ONBOARDING_OPERATOR_IDS", ""):
        raise RuntimeError("V26_ACCEPTANCE_OPERATOR_REJECTED")

    try:
        url = urlsplit(values.get("V2_DATABASE_URL", ""))
        password = unquote(url.password or "")
        valid = (
            url.scheme == "postgresql+psycopg"
            and url.hostname == "127.0.0.1"
            and url.port == 55433
            and url.path == "/mikrotik_v26_acceptance"
            and unquote(url.username or "") == "v26_acceptance"
            and len(password) >= 20
            and not any(ord(c) < 32 for c in password)
            and "REPLACE_" not in password
            and "PLACEHOLDER" not in password
            and not url.query
            and not url.fragment
        )
    except Exception:
        valid = False

    if not valid:
        raise RuntimeError("V26_ACCEPTANCE_DATABASE_REJECTED")

    return True
