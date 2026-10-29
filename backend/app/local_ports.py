"""Explicit loopback-only V2 development endpoints; never scan or steal ports."""
import os


def local_port(name, default):
    raw = os.environ.get(name, str(default))
    if not raw.isascii() or not raw.isdecimal() or not 1024 <= int(raw) <= 65535:
        raise ValueError(f'{name}: 1024–65535 arasında bir port gerekli.')
    return int(raw)


def api_port():
    return local_port('V2_API_PORT', 8000)


def ui_port():
    port = local_port('V2_UI_PORT', 5173)
    if port == api_port():
        raise ValueError('V2_API_PORT ve V2_UI_PORT farklı olmalı.')
    return port


def api_base():
    return f'http://127.0.0.1:{api_port()}'


def ui_base():
    return f'http://127.0.0.1:{ui_port()}'
