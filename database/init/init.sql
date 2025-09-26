-- Create the traffic_db database if it doesn't exist
SELECT 'CREATE DATABASE traffic_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'traffic_db')\gexec

-- Connect to the new database to create extensions and users
\c traffic_db

-- Create user and grant privileges
CREATE USER postgres WITH PASSWORD 'casa1234';
GRANT ALL PRIVILEGES ON DATABASE traffic_db TO postgres;
ALTER ROLE postgres SET client_encoding TO 'utf8';
ALTER ROLE postgres SET default_transaction_isolation TO 'read committed';
ALTER ROLE postgres SET timezone TO 'UTC';

-- Grant all privileges on all tables in the public schema to the user
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
