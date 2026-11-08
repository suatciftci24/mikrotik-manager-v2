-- Add the existing router-scoped OPERATOR capability to isolated identity stores.
-- This migration is prepared only; it must be applied through the approved local
-- maintenance flow and is intentionally not run by application startup.
DO $migration$
DECLARE
    target_schema text;
BEGIN
    FOREACH target_schema IN ARRAY ARRAY['v2_demo', 'v26_acceptance'] LOOP
        IF to_regclass(format('%I.users', target_schema)) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE %I.users DROP CONSTRAINT IF EXISTS users_role_check', target_schema);
            EXECUTE format(
                'ALTER TABLE %I.users ADD CONSTRAINT users_role_check CHECK (role IN (''ADMIN'', ''OPERATOR'', ''VIEWER''))',
                target_schema
            );
        END IF;
    END LOOP;
END
$migration$;
