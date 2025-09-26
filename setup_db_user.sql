-- PostgreSQL Setup Script for Traffic Prediction System
-- This script properly configures the database user and password

-- Connect to the PostgreSQL container and run this script

-- First, set the password for traffic_user
ALTER USER traffic_user PASSWORD 'traffic_password';

-- Create the traffic_db database if it doesn't exist
CREATE DATABASE traffic_db OWNER traffic_user;

-- Grant all privileges to traffic_user on traffic_db
GRANT ALL PRIVILEGES ON DATABASE traffic_db TO traffic_user;

-- Show current configuration
SELECT usename, usesuper, usecreatedb FROM pg_user WHERE usename = 'traffic_user';

-- Test the connection settings
\c traffic_db traffic_user

-- Display connection info
SELECT current_user, current_database(), version();