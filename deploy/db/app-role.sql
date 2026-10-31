-- Make the app's database role a non-superuser that owns the database and its
-- tables. Row-level security keeps each business's data apart, and PostgreSQL
-- skips it for superusers, so the app must never connect as one.
--
--   psql -v app_role=chhapakhata_app [-v app_password=...] -d chhapakhata -f app-role.sql
--
-- Run it as a superuser. Safe to run again (new install, upgrade, after a restore).
\set ON_ERROR_STOP on

SELECT format('CREATE ROLE %I LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOBYPASSRLS', :'app_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') \gexec

\if :{?app_password}
ALTER ROLE :"app_role" PASSWORD :'app_password';
\endif

SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'app_role') \gexec

-- Tables first: their sequences follow them. Then any remaining sequences and views.
SELECT format('ALTER TABLE public.%I OWNER TO %I', tablename, :'app_role')
FROM pg_tables WHERE schemaname = 'public' AND tableowner <> :'app_role' \gexec

SELECT format(
    CASE c.relkind WHEN 'S' THEN 'ALTER SEQUENCE public.%I OWNER TO %I'
                   ELSE 'ALTER VIEW public.%I OWNER TO %I' END,
    c.relname, :'app_role')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('S', 'v')
  AND pg_get_userbyid(c.relowner) <> :'app_role' \gexec
