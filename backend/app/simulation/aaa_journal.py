"""Isolated SQLite journal prototype. Explicit connection only; never opens application DB."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from app.integrations.aaa_contracts import ReadContract, AaaSnapshot, PreviewScope, require_preview_scope


class JournalRequest(ReadContract):
    tenant_id: str = Field(min_length=1, max_length=80)
    request_id: UUID
    correlation_id: UUID
    actor_id: str = Field(min_length=1, max_length=160)
    snapshot: AaaSnapshot
    target: Literal['RADIUS'] = 'RADIUS'

    def fingerprint(self):
        content = self.model_dump(mode='json', exclude={'request_id'})
        return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class JournalEvent(ReadContract):
    state: Literal['PLANNED', 'MODELED', 'FAILED', 'UNCERTAIN', 'COMPENSATING', 'COMPENSATED', 'RECONCILIATION']
    expected_revision: int = Field(ge=1)
    at: datetime

    @field_validator('at')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('UTC-aware time required')
        return value.astimezone(timezone.utc)


class JournalConflict(ValueError):
    pass


# No provider invocation, automatic retries, rollback executor or account mutations.
EDGES = {
    'RESERVED': {'PLANNED', 'FAILED'},
    'PLANNED': {'MODELED', 'FAILED', 'UNCERTAIN'},
    'UNCERTAIN': {'RECONCILIATION'},
    'MODELED': {'COMPENSATING', 'RECONCILIATION'},
    'COMPENSATING': {'COMPENSATED', 'RECONCILIATION'},
    'FAILED': set(), 'COMPENSATED': set(), 'RECONCILIATION': set(),
}


class IsolatedJournal:
    """Caller supplies a disposable SQLite connection. No implicit schema/init or IO on import."""
    def __init__(self, connection: sqlite3.Connection):
        if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
            raise ValueError('Idle isolated SQLite connection required')
        self.connection = connection
        self.connection.execute('PRAGMA foreign_keys=ON')

    def initialize(self):
        # Explicit isolated schema only, not a PostgreSQL migration.
        self.connection.executescript('''
        CREATE TABLE operations (
          tenant TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
          actor TEXT NOT NULL, store TEXT NOT NULL, account TEXT NOT NULL,
          account_revision INTEGER NOT NULL, correlation TEXT NOT NULL,
          state TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1),
          PRIMARY KEY(tenant, request_id),
          UNIQUE(tenant, store, account, account_revision)
        );
        CREATE TABLE events (
          tenant TEXT NOT NULL, request_id TEXT NOT NULL, revision INTEGER NOT NULL,
          state TEXT NOT NULL, at TEXT NOT NULL, correlation TEXT NOT NULL, actor TEXT NOT NULL,
          PRIMARY KEY(tenant, request_id, revision),
          FOREIGN KEY(tenant, request_id) REFERENCES operations(tenant, request_id)
        );
        ''')
        self.connection.execute('PRAGMA foreign_keys=ON')

    def _authorized(self, request, scope):
        require_preview_scope(request.snapshot, scope)
        if request.tenant_id != scope.tenant_id or request.actor_id != scope.actor_id:
            raise PermissionError('JOURNAL_SCOPE_DENIED')

    def _row(self, request):
        return self.connection.execute(
            'SELECT fingerprint,state,revision,actor FROM operations WHERE tenant=? AND request_id=?',
            (request.tenant_id, str(request.request_id))).fetchone()

    def _match(self, request, row):
        if row is None or row[0] != request.fingerprint() or row[3] != request.actor_id:
            raise JournalConflict('IDEMPOTENCY_CONFLICT')

    def reserve(self, request: JournalRequest, scope: PreviewScope, at: datetime):
        self._authorized(request, scope)
        clock = JournalEvent(state='PLANNED', expected_revision=1, at=at).at.isoformat()
        conn = self.connection
        conn.execute('BEGIN IMMEDIATE')
        try:
            row = self._row(request)
            if row:
                self._match(request, row)
                conn.commit()
                return row[1], row[2], True
            ref = request.snapshot.reference
            conn.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?)',
                         (request.tenant_id, str(request.request_id), request.fingerprint(), request.actor_id,
                          ref.store, ref.account_id, ref.revision, str(request.correlation_id), 'RESERVED', 1))
            conn.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?)',
                         (request.tenant_id, str(request.request_id), 1, 'RESERVED', clock,
                          str(request.correlation_id), request.actor_id))
            conn.commit()
            return 'RESERVED', 1, False
        except sqlite3.IntegrityError:
            conn.rollback()
            raise JournalConflict('ACCOUNT_REVISION_ALREADY_RESERVED') from None
        except BaseException:
            conn.rollback()
            raise

    def advance(self, request: JournalRequest, scope: PreviewScope, event: JournalEvent):
        self._authorized(request, scope)
        conn = self.connection
        conn.execute('BEGIN IMMEDIATE')
        try:
            row = self._row(request)
            self._match(request, row)
            if row[2] != event.expected_revision:
                raise JournalConflict('OPERATION_REVISION_CONFLICT')
            if event.state not in EDGES[row[1]]:
                raise JournalConflict('INVALID_STATE_TRANSITION')
            revision = row[2] + 1
            changed = conn.execute('UPDATE operations SET state=?,revision=? WHERE tenant=? AND request_id=? AND revision=?',
                                   (event.state, revision, request.tenant_id, str(request.request_id), row[2]))
            if changed.rowcount != 1:
                raise JournalConflict('OPERATION_REVISION_CONFLICT')
            conn.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?)',
                         (request.tenant_id, str(request.request_id), revision, event.state,
                          event.at.isoformat(), str(request.correlation_id), request.actor_id))
            conn.commit()
            return event.state, revision
        except BaseException:
            conn.rollback()
            raise

    def history(self, request: JournalRequest, scope: PreviewScope):
        self._authorized(request, scope)
        self._match(request, self._row(request))
        return tuple(self.connection.execute(
            'SELECT revision,state,at,correlation,actor FROM events WHERE tenant=? AND request_id=? ORDER BY revision',
            (request.tenant_id, str(request.request_id))))
