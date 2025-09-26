-- Script to create traffic_user and traffic_db in LOCAL PostgreSQL
-- Run this in your local PostgreSQL (pgAdmin or psql)

-- 1. Create the traffic_user with password
CREATE USER traffic_user WITH PASSWORD 'traffic_password';

-- 2. Grant necessary privileges to the user
ALTER USER traffic_user CREATEDB;
ALTER USER traffic_user WITH SUPERUSER;

-- 3. Create the traffic_db database
CREATE DATABASE traffic_db OWNER traffic_user;

-- 4. Grant all privileges on the database
GRANT ALL PRIVILEGES ON DATABASE traffic_db TO traffic_user;

-- 5. Connect to the new database and create the schema
\c traffic_db

-- 6. Create the traffic schema
CREATE SCHEMA IF NOT EXISTS traffic;

-- 7. Grant usage on the schema
GRANT ALL ON SCHEMA traffic TO traffic_user;

-- 8. Set the default search path
ALTER DATABASE traffic_db SET search_path = traffic, public;

-- Verification queries
SELECT usename, usesuper, usecreatedb FROM pg_user WHERE usename = 'traffic_user';
SELECT datname FROM pg_database WHERE datname = 'traffic_db';

-- Show connection info
SELECT current_user, current_database();