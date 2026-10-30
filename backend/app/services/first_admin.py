"""One-time LOCAL account creation. Invoked by the owner-only TTY CLI, never HTTP/startup."""
import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_core import PydanticCustomError
from sqlalchemy import text

from app.adapters.demo_subscriptions import PostgresDemoStore, storage_errors
from app.core.authorization import PERMISSIONS
from app.services import identity
from app.services.demo_data import ROUTERS
from app.services.identity_setup import inspect_setup, schema_name

ROOT = Path(__file__).resolve().parents[3]


class SetupBlocked(Exception):
    """Static, public diagnostic only. Never wrap SQL/credentials/input values."""


def require(condition, code):
    if not condition:
        raise SetupBlocked(code)


class FirstAdminIdentity(BaseModel):
    """Validate public fields before collecting any secret. Never normalize a password."""
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,64}$')
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=180, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

    @field_validator('username', 'name', 'email', mode='before')
    @classmethod
    def normalize_public_text(cls, value):
        if isinstance(value, str):
            if any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise PydanticCustomError('public_text_control', 'Kontrol karakteri kullanılamaz')
            return value.strip(' ')
        return value

    @field_validator('username', 'name', 'email')
    @classmethod
    def public_text(cls, value):
        if value != value.strip():
            raise PydanticCustomError('public_text_whitespace', 'Alan başında veya sonunda boşluk kullanılamaz')
        if value.casefold() in ('demo', 'demo-user'):
            raise PydanticCustomError('reserved_demo_identity', 'Demo kimliği kullanılamaz')
        return value


class FirstAdminInput(FirstAdminIdentity):
    password: SecretStr = Field(repr=False, exclude=True)

    @field_validator('password')
    @classmethod
    def strong_password(cls, value):
        raw = value.get_secret_value()
        try:
            raw.encode('utf-8')
        except UnicodeError:
            raise PydanticCustomError('password_encoding', 'Parola geçerli UTF-8 olmalıdır') from None
        if not identity.local_password_valid(raw):
            if len(raw) < 14:
                raise PydanticCustomError('password_too_short', 'Parola en az 14 karakter olmalıdır')
            if len(raw) > 128 or len(raw.encode('utf-8')) > 1024:
                raise PydanticCustomError('password_too_long', 'Parola en çok 128 karakter / 1024 UTF-8 bayt olmalıdır')
            if not raw.strip():
                raise PydanticCustomError('password_blank', 'Parola yalnızca boşluklardan oluşamaz')
            raise PydanticCustomError('password_control', 'Parolada satır sonu veya NUL kullanılamaz')
        return value


def local_owner(root=ROOT):
    """The OS account owning THIS repo and its isolated cluster authorizes setup."""
    uid = os.getuid()
    require(uid > 0 and os.geteuid() == uid, 'LOCAL_OWNER_REQUIRED')
    for path in (root, root / '.local', root / '.local/postgres-v2-demo'):
        require(not path.is_symlink(), 'LOCAL_PATH_REJECTED')
        info = path.stat()
        require(path.is_dir() and info.st_uid == uid and not info.st_mode & 0o022,
                'LOCAL_OWNER_REQUIRED')
    require((root / 'AGENTS.md').is_file() and (root / 'dev-db.sh').is_file(), 'V2_ROOT_REQUIRED')
    return uid


def verify_target(connection, root=ROOT):
    row = connection.execute(text('SELECT current_database(), current_user, inet_server_port()')).one()
    require(tuple(row) == ('mikrotik_manager_v2', 'v2_local', 55432), 'V2_DATABASE_REJECTED')
    directory = connection.execute(text('SHOW data_directory')).scalar_one()
    require(Path(directory).resolve() == (root / '.local/postgres-v2-demo').resolve(), 'V2_CLUSTER_REJECTED')


class FirstAdminStore:
    def __init__(self, engine, schema='v2_demo'):
        self.schema = schema_name(schema)
        self.store = PostgresDemoStore(engine, self.schema)  # Reject non-V2 targets before IO.
        self.engine = engine

    def _check(self, connection):
        verify_target(connection)
        self.store._verify(connection)

    @storage_errors
    def status(self):
        with self.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                self._check(connection)
                return inspect_setup(connection, self.schema)

    def _upgrade(self, connection, state):
        # Explicit versioned additive SQL. Never run at app import/startup or from an endpoint.
        versions = ([] if state.users_ready else ['004_demo_identity.sql'])
        if not state.modern:
            versions.append('009_first_local_admin.sql')
        for version in versions:
            sql = (ROOT / 'migrations/versions' / version).read_text().replace('v2_demo.', self.schema + '.')
            for statement in sql.split(';'):
                if statement.strip():
                    connection.execute(text(statement))

    @storage_errors
    def create(self, payload: FirstAdminInput, local_uid: int):
        require(type(local_uid) is int and local_uid > 0 and local_uid == os.getuid(), 'LOCAL_OWNER_REQUIRED')
        # Callers cannot bypass validation with a model constructed without validators.
        payload = FirstAdminInput.model_validate({**payload.model_dump(), 'password': payload.password})
        with self.engine.begin() as connection:
            self._check(connection)
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-user-management'))"))
            connection.execute(text(f'SELECT version FROM {self.schema}.schema_state WHERE version=1 FOR UPDATE'))
            state = inspect_setup(connection, self.schema)
            require(not state.closed, 'FIRST_ADMIN_SETUP_CLOSED')
            self._upgrade(connection, state)
            # Recheck after the schema upgrade. Never promote/rewrite a demo account.
            state = inspect_setup(connection, self.schema)
            require(not state.closed, 'FIRST_ADMIN_SETUP_CLOSED')
            exists = connection.execute(text(f'SELECT 1 FROM {self.schema}.users WHERE lower(username)=lower(:username)'),
                                        {'username': payload.username}).scalar_one_or_none()
            require(exists is None, 'USERNAME_UNAVAILABLE')
            record = dict(id='v2-user-' + str(uuid4()), username=payload.username, name=payload.name,
                          email=payload.email, role='ADMIN', active=True, revision=0, account_origin='LOCAL',
                          permissions={r['id']: {p: True for p in PERMISSIONS} for r in ROUTERS})
            connection.execute(text(f'''INSERT INTO {self.schema}.users
                (id,username,name,email,role,active,password_hash,permissions,revision,account_origin)
                VALUES (:id,:username,:name,:email,:role,:active,:password_hash,CAST(:permissions AS jsonb),:revision,:account_origin)'''),
                {**record, 'permissions': json.dumps(record['permissions']),
                 'password_hash': identity.hash_password(payload.password.get_secret_value(), real_account=True)})
            public = identity.public_user(record, True, bootstrap_closed=True)
            connection.execute(text(f'''INSERT INTO {self.schema}.user_audit
                (id,actor_id,target_id,operation,previous_values,new_values,result,fingerprint,response)
                VALUES (:id,:actor,:target,'FIRST_ADMIN_CREATE',NULL,CAST(:new AS jsonb),'SUCCESS','LOCAL_TTY_BOOTSTRAP',CAST(:new AS jsonb))'''),
                dict(id=str(uuid4()), actor='local-os:' + str(local_uid), target=record['id'], new=json.dumps(public)))
            connection.execute(text(f'''INSERT INTO {self.schema}.first_admin_setup(singleton,admin_id,local_operator_uid)
                VALUES (1,:id,:uid)'''), {'id': record['id'], 'uid': local_uid})
            connection.execute(text(f'UPDATE {self.schema}.schema_state SET identity_initialized=true,first_admin_initialized=true WHERE version=1'))
        # Context manager has committed both the account/audit and permanent seal.
        return public
