-- Prepared read-only projection only. Not run by application/startup/deployment.
-- Requires a separately authorized exporter with column SELECT privileges.
-- No grant, role or schema changes here. Fail on permission/source errors;
-- never fall back to an administrator account or a metadata timestamp.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
WITH inventory AS (
    SELECT id, name, identity, model, routeros_version
    FROM public.routers ORDER BY id LIMIT 2001
), latest AS (
    SELECT h.* FROM inventory r
    JOIN LATERAL (
        SELECT id, router_id, sampled_at, cpu_load_percent,
               memory_used_percent, internet_success
        FROM public.router_health_samples h WHERE h.router_id = r.id
        ORDER BY sampled_at DESC, id DESC LIMIT 1
    ) h ON true
)
SELECT json_build_object(
    'source', 'V1_INVENTORY_EXPORT',
    'items', coalesce((SELECT json_agg(json_build_object(
        'id', id::text, 'name', name, 'identity', identity,
        'model', model, 'routeros_version', routeros_version) ORDER BY id)
        FROM inventory), '[]'::json),
    'health_samples', coalesce((SELECT json_agg(json_build_object(
        'id', id::text, 'router_id', router_id::text, 'sampled_at', sampled_at,
        'cpu_load_percent', cpu_load_percent, 'memory_used_percent', memory_used_percent,
        'internet_success', internet_success) ORDER BY router_id)
        FROM latest), '[]'::json)
);
ROLLBACK;
