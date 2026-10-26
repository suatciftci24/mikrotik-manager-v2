-- V2-only initial schema design. This file is intentionally not auto-applied.
CREATE TABLE roles (
    id uuid PRIMARY KEY,
    name varchar(64) NOT NULL UNIQUE,
    description varchar(240) NOT NULL DEFAULT '',
    is_system boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE TABLE permissions (
    id uuid PRIMARY KEY,
    key varchar(120) NOT NULL UNIQUE,
    module varchar(40) NOT NULL,
    description varchar(240) NOT NULL DEFAULT ''
);
CREATE TABLE role_permissions (
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
CREATE TABLE panel_users (
    id uuid PRIMARY KEY,
    email varchar(254) NOT NULL UNIQUE,
    display_name varchar(120) NOT NULL,
    password_hash varchar(255) NOT NULL,
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active boolean NOT NULL DEFAULT true,
    is_demo boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE TABLE routers (
    id uuid PRIMARY KEY,
    name varchar(120) NOT NULL,
    management_address varchar(64) NOT NULL,
    site varchar(120) NOT NULL DEFAULT '',
    model varchar(80) NOT NULL DEFAULT 'Unspecified',
    routeros_version varchar(40) NOT NULL DEFAULT '',
    status varchar(24) NOT NULL DEFAULT 'UNKNOWN',
    cpu_percent integer NOT NULL DEFAULT 0,
    memory_percent integer NOT NULL DEFAULT 0,
    subscriber_count integer NOT NULL DEFAULT 0,
    is_enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX ix_routers_status_name ON routers(status, name);
CREATE TABLE customers (
    id uuid PRIMARY KEY,
    full_name varchar(160) NOT NULL,
    contact_email varchar(254),
    contact_phone varchar(40),
    status varchar(24) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE TABLE subscription_plans (
    id uuid PRIMARY KEY,
    name varchar(120) NOT NULL UNIQUE,
    download_mbps integer NOT NULL,
    upload_mbps integer NOT NULL,
    monthly_price numeric(10, 2) NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE TABLE subscriber_accounts (
    id uuid PRIMARY KEY,
    customer_id uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    router_id uuid NOT NULL REFERENCES routers(id) ON DELETE RESTRICT,
    plan_id uuid NOT NULL REFERENCES subscription_plans(id) ON DELETE RESTRICT,
    username varchar(96) NOT NULL,
    authoritative_source varchar(6) NOT NULL CHECK (authoritative_source IN ('LOCAL', 'RADIUS')),
    local_secret_ref varchar(180),
    radius_identity varchar(180),
    status varchar(24) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_subscriber_router_username UNIQUE (router_id, username),
    CONSTRAINT ck_subscriber_exactly_one_authority CHECK (
      (authoritative_source = 'LOCAL' AND local_secret_ref IS NOT NULL AND radius_identity IS NULL) OR
      (authoritative_source = 'RADIUS' AND radius_identity IS NOT NULL AND local_secret_ref IS NULL)
    )
);
CREATE INDEX ix_subscriber_status_source ON subscriber_accounts(status, authoritative_source);
CREATE TABLE subscriber_events (
    id uuid PRIMARY KEY,
    subscriber_account_id uuid NOT NULL REFERENCES subscriber_accounts(id) ON DELETE RESTRICT,
    event_type varchar(80) NOT NULL,
    actor_id uuid REFERENCES panel_users(id) ON DELETE SET NULL,
    details json NOT NULL DEFAULT '{}'::json,
    occurred_at timestamptz NOT NULL
);
CREATE INDEX ix_subscriber_events_subscriber_account_id ON subscriber_events(subscriber_account_id);
CREATE TABLE audit_logs (
    id uuid PRIMARY KEY,
    actor_id uuid REFERENCES panel_users(id) ON DELETE SET NULL,
    action varchar(100) NOT NULL,
    resource_type varchar(80) NOT NULL,
    resource_id varchar(80),
    outcome varchar(24) NOT NULL,
    request_id varchar(80),
    details json NOT NULL DEFAULT '{}'::json,
    occurred_at timestamptz NOT NULL
);
CREATE INDEX ix_audit_logs_actor_id ON audit_logs(actor_id);
CREATE INDEX ix_audit_logs_request_id ON audit_logs(request_id);
