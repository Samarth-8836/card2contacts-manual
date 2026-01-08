-- ==========================================
-- DIGICARD ENTERPRISE - DATABASE INITIALIZATION
-- ==========================================
-- This script initializes the PostgreSQL database
-- It's automatically run when the database container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set timezone
SET timezone = 'UTC';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE digicard_enterprise TO digicard_admin;

-- Note: SQLModel will create tables automatically via Alembic migrations
-- This file is for any initial database setup only
