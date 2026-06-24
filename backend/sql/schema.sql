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
