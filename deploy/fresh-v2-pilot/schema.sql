-- Deterministic structural signature; deliberately independent of OIDs/owner names.
-- Includes every non-system schema/relation, columns, defaults, constraints,
-- index definitions, routines, triggers, policies and extensions.
SELECT jsonb_build_object(
 'schemas',(SELECT jsonb_agg(nspname ORDER BY nspname) FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'),
 'relations',(SELECT jsonb_agg(jsonb_build_array(n.nspname,c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity) ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'columns',(SELECT jsonb_agg(jsonb_build_array(n.nspname,c.relname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid)) ORDER BY n.nspname,c.relname,a.attnum) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum WHERE a.attnum>0 AND NOT a.attisdropped AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'constraints',(SELECT jsonb_agg(jsonb_build_array(n.nspname,c.relname,k.conname,k.contype,k.convalidated,pg_get_constraintdef(k.oid)) ORDER BY n.nspname,c.relname,k.conname) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'indexes',(SELECT jsonb_agg(jsonb_build_array(schemaname,indexname,indexdef) ORDER BY schemaname,indexname) FROM pg_indexes WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema'),
 'routines',(SELECT jsonb_agg(jsonb_build_array(n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),p.prosrc,p.prosecdef) ORDER BY n.nspname,p.proname,p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'triggers',(SELECT jsonb_agg(pg_get_triggerdef(t.oid) ORDER BY t.tgname) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'policies',(SELECT jsonb_agg(to_jsonb(p) ORDER BY schemaname,tablename,policyname) FROM pg_policies p WHERE schemaname !~ '^pg_'),
 'extensions',(SELECT jsonb_agg(jsonb_build_array(extname,extversion) ORDER BY extname) FROM pg_extension)
)::text AS schema_json;
