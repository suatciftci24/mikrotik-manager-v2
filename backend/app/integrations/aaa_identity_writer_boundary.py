"""Disabled-by-default AAA identity/writer boundary.

Preparation only: no API registration, database connection,
router access, RADIUS access, or live writer.
"""
from dataclasses import dataclass
from typing import Callable


class AaaBoundaryDisabled(PermissionError):
    pass


@dataclass(frozen=True)
class AaaIdentityWriterBoundary:
    identity_reader: Callable
    authorization_reader: Callable
    owner_reader: Callable
    writer: Callable

    def execute(self, *args, **kwargs):
        raise AaaBoundaryDisabled(
            "AAA_REAL_IDENTITY_WRITER_NOT_ENABLED"
        )
