-- Existing events retain their identity and revision. Their field values are unknown.
ALTER TABLE v2_router_workspace.audit ADD COLUMN changes json;
