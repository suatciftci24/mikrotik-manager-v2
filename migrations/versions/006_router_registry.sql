-- Explicit V2 registry schema only. No device IO, demo mutation, seed or startup migration.
CREATE TABLE v2_registered_routers (
    id varchar(48) PRIMARY KEY,
    name varchar(120) NOT NULL,
    management_address varchar(64) NOT NULL,
    port integer NOT NULL CHECK (port BETWEEN 1024 AND 65535 AND port <> 8728),
    configuration json NOT NULL,
    metadata_snapshot json NOT NULL,
    credential_ref varchar(36) NOT NULL,
    revision integer NOT NULL,
    last_checked_at varchar(40) NOT NULL,
    last_success_at varchar(40) NOT NULL,
    last_error varchar(200),
    UNIQUE (management_address, port)
);
CREATE TABLE v2_router_verifications (
    id varchar(36) PRIMARY KEY,
    actor_id varchar(80) NOT NULL,
    state varchar(16) NOT NULL,
    target_router_id varchar(48),
    expected_revision integer NOT NULL,
    snapshot json NOT NULL,
    credential_ref varchar(36) NOT NULL,
    created_at varchar(40) NOT NULL,
    expires_at varchar(40) NOT NULL,
    error_code varchar(200),
    saved_router_id varchar(48)
);
CREATE INDEX ix_v2_router_verifications_actor_id ON v2_router_verifications(actor_id);
CREATE TABLE v2_router_registry_audit (
    id varchar(36) PRIMARY KEY,
    actor_id varchar(80) NOT NULL,
    router_id varchar(48),
    verification_id varchar(36) NOT NULL,
    action varchar(40) NOT NULL,
    occurred_at varchar(40) NOT NULL,
    details json NOT NULL
);
CREATE INDEX ix_v2_router_registry_audit_router_id ON v2_router_registry_audit(router_id);
CREATE INDEX ix_v2_registered_routers_name ON v2_registered_routers(name);
CREATE INDEX ix_v2_registered_routers_check ON v2_registered_routers(last_error,last_success_at);
CREATE INDEX ix_v2_router_verifications_expiry ON v2_router_verifications(state,expires_at);
CREATE INDEX ix_v2_router_registry_audit_time ON v2_router_registry_audit(router_id,occurred_at);
