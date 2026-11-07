-- Metadata only. Does not connect or change schema/data.
-- Operator must FIRST verify the actual V2.6 DB/role/port and application build.
-- Do not run against V1/V2.5/Fresh Pilot or infer a target from this file.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '1s';

SELECT current_database() AS database_name, current_user AS role_name,
       inet_server_port() AS server_port, current_setting('transaction_read_only') AS read_only;

WITH wanted(schema_name, relation_name) AS (
 VALUES ('v26_acceptance','settings_records'),('v26_acceptance','settings_audit'),
        ('v2_demo','settings_records'),('v2_demo','settings_audit')
)
SELECT w.schema_name,w.relation_name,n.oid IS NOT NULL AS schema_exists,
       c.oid IS NOT NULL AS relation_exists,c.relkind,
       CASE WHEN n.oid IS NOT NULL THEN has_schema_privilege(current_user,n.oid,'USAGE') END AS schema_usage,
       CASE WHEN c.oid IS NOT NULL THEN has_table_privilege(current_user,c.oid,'SELECT') END AS can_select
FROM wanted w LEFT JOIN pg_namespace n ON n.nspname=w.schema_name
LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=w.relation_name
ORDER BY w.schema_name,w.relation_name;

SELECT n.nspname AS schema_name,c.relname AS relation_name,a.attname AS column_name,
       format_type(a.atttypid,a.atttypmod) AS column_type,a.attnotnull AS not_null
FROM pg_namespace n JOIN pg_class c ON c.relnamespace=n.oid
JOIN pg_attribute a ON a.attrelid=c.oid
WHERE n.nspname IN ('v26_acceptance','v2_demo') AND a.attnum>0 AND NOT a.attisdropped
  AND (c.relname IN ('settings_records','settings_audit')
       OR c.relname='schema_state' AND a.attname IN ('version','marker','settings_initialized'))
ORDER BY n.nspname,c.relname,a.attnum;

SELECT n.nspname AS schema_name,c.relname AS relation_name,k.contype,
       pg_get_constraintdef(k.oid) AS constraint_definition
FROM pg_namespace n JOIN pg_class c ON c.relnamespace=n.oid
JOIN pg_constraint k ON k.conrelid=c.oid
WHERE n.nspname IN ('v26_acceptance','v2_demo')
  AND c.relname IN ('settings_records','settings_audit')
ORDER BY n.nspname,c.relname,k.conname;

SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
WHERE schemaname IN ('v26_acceptance','v2_demo')
  AND tablename IN ('settings_records','settings_audit')
ORDER BY schemaname,tablename,indexname;
ROLLBACK;
