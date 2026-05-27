-- Bootstrapping extensions executed once by the Postgres container on first
-- start (mounted into /docker-entrypoint-initdb.d/). Alembic migrations
-- handle table DDL.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
