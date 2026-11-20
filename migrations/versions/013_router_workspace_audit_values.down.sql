-- Roll back the application first and archive audit values before dropping this column.
ALTER TABLE v2_router_workspace.audit DROP COLUMN changes;
