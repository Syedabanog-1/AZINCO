-- AZINCO database roles. Executed by 01-roles.sh with psql variables:
--   :db, :migrator_pw, :app_pw, :worker_pw, :ledger_pw, :audit_pw, :readonly_pw
-- Idempotence is not needed: Postgres runs init scripts only on an empty data volume.

\set ON_ERROR_STOP on

-- 1. Migration owner -------------------------------------------------------------
CREATE ROLE azinco_migrator LOGIN PASSWORD :'migrator_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- 2. Runtime roles: never owners, never BYPASSRLS ---------------------------------
CREATE ROLE azinco_app      LOGIN PASSWORD :'app_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE azinco_worker   LOGIN PASSWORD :'worker_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE azinco_ledger   LOGIN PASSWORD :'ledger_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE azinco_audit    LOGIN PASSWORD :'audit_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE azinco_readonly LOGIN PASSWORD :'readonly_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;

-- 3. Database ownership & connect rights -----------------------------------------
ALTER DATABASE :"db" OWNER TO azinco_migrator;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db" TO azinco_migrator;
GRANT CONNECT ON DATABASE :"db"
  TO azinco_app, azinco_worker, azinco_ledger, azinco_audit, azinco_readonly;

-- 4. Lock down the public schema --------------------------------------------------
-- Nobody but the migrator may create objects in "public"; app roles may only USE it
-- (extension functions such as gen_random_uuid() live there).
ALTER SCHEMA public OWNER TO azinco_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public
  TO azinco_app, azinco_worker, azinco_ledger, azinco_audit, azinco_readonly;

-- 5. Safe session defaults --------------------------------------------------------
ALTER ROLE azinco_app      SET statement_timeout = '30s';
ALTER ROLE azinco_worker   SET statement_timeout = '120s';
ALTER ROLE azinco_ledger   SET statement_timeout = '30s';
ALTER ROLE azinco_readonly SET default_transaction_read_only = on;
ALTER ROLE azinco_readonly SET statement_timeout = '60s';

-- 6. Tenant context default: no tenant => RLS policies (Step 0.6) return zero rows.
ALTER DATABASE :"db" SET app.tenant_id = '';
ALTER DATABASE :"db" SET app.user_id = '';
