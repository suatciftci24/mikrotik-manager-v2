CREATE SCHEMA v2_migrations;
CREATE TABLE v2_migrations.applied (
 position integer PRIMARY KEY CHECK(position BETWEEN 1 AND 9),
 revision text NOT NULL UNIQUE,
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE v2_migrations.installation (
 singleton integer PRIMARY KEY CHECK(singleton=1),
 profile text NOT NULL CHECK(profile='fresh-v2-pilot'),
 manifest_sha256 text NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
 schema_sha256 text NOT NULL CHECK(schema_sha256 ~ '^[0-9a-f]{64}$'),
 completed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
