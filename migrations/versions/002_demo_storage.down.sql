-- Explicit rollback ONLY for the isolated V2 development demo schema.
-- Export demo data first: this removes its synthetic records/history/request keys.
DROP SCHEMA v2_demo CASCADE;
