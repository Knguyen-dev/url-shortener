-- Create users table
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY, 
  email TEXT NOT NULL UNIQUE,
  full_name VARCHAR(32) NOT NULL,
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sessions table
-- TODO: Can update this to only use user_id as primary key
CREATE TABLE IF NOT EXISTS sessions (
    user_id INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW() -- for idle timeout
);

