-- MeetMind database schema for Supabase PostgreSQL
-- Run this in the Supabase SQL Editor before testing Phase 1

-- Profiles table (linked to Supabase Auth users)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    is_pro BOOLEAN NOT NULL DEFAULT FALSE,
    pro_until TIMESTAMPTZ,
    meetings_used INTEGER NOT NULL DEFAULT 0,
    razorpay_subscription_id TEXT
);

-- Meetings table
CREATE TABLE IF NOT EXISTS meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Untitled Meeting',
    transcript TEXT,
    mom JSONB,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'done', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_meetings_user_id ON meetings(user_id);
CREATE INDEX IF NOT EXISTS idx_meetings_created_at ON meetings(created_at DESC);

-- Row Level Security (enable in Phase 2 with auth)
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS; user policies added in Phase 2

-- Phase 3 Hardening additions

-- Error logs table
CREATE TABLE IF NOT EXISTS error_logs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  endpoint text,
  error_type text,
  message text,
  user_id uuid REFERENCES profiles(id) ON DELETE SET NULL,
  ip_address text,
  request_id text,
  created_at timestamptz DEFAULT now()
);

-- Suspicious activity log
CREATE TABLE IF NOT EXISTS security_logs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  event_type text NOT NULL,  -- 'failed_login', 'injection_attempt', 'rate_limit_hit'
  ip_address text,
  user_id uuid REFERENCES profiles(id) ON DELETE SET NULL,
  details jsonb,
  created_at timestamptz DEFAULT now()
);

-- Failed login tracking
CREATE TABLE IF NOT EXISTS failed_logins (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text,
  ip_address text,
  attempted_at timestamptz DEFAULT now()
);

-- Index for fast IP lookups
CREATE INDEX IF NOT EXISTS idx_failed_logins_ip ON failed_logins(ip_address);
CREATE INDEX IF NOT EXISTS idx_failed_logins_email ON failed_logins(email);
CREATE INDEX IF NOT EXISTS idx_security_logs_ip ON security_logs(ip_address);

-- Auto-cleanup old logs (keep 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS void AS $$
BEGIN
  DELETE FROM error_logs WHERE created_at < now() - interval '90 days';
  DELETE FROM security_logs WHERE created_at < now() - interval '90 days';
  DELETE FROM failed_logins WHERE attempted_at < now() - interval '7 days';
END;
$$ LANGUAGE plpgsql;

-- Add updated_at to profiles
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS profiles_updated_at ON profiles;
CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS meetings_updated_at ON meetings;
CREATE TRIGGER meetings_updated_at
  BEFORE UPDATE ON meetings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
