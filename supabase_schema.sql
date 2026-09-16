-- Supabase SQL Schema for Rabbi David Backend (https://rabbidavid.org)
-- Run this script in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run)

-- 1. Users Table (Mirror of SQLite users)
CREATE TABLE IF NOT EXISTS public.users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    salt TEXT,
    name TEXT,
    email_verified INTEGER DEFAULT 0,
    verification_token TEXT,
    created DOUBLE PRECISION NOT NULL,
    updated DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow full access to service_role on users"
    ON public.users FOR ALL
    USING (auth.role() = 'service_role');

-- 2. Sessions Table (Mirror of SQLite sessions)
CREATE TABLE IF NOT EXISTS public.sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    data JSONB NOT NULL,
    updated DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions(user_id);
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow full access to service_role on sessions"
    ON public.sessions FOR ALL
    USING (auth.role() = 'service_role');

-- 3. Orders Table (Mirror of SQLite orders)
CREATE TABLE IF NOT EXISTS public.orders (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    email TEXT NOT NULL,
    book_id TEXT,
    amount INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'usd',
    delivery_status TEXT DEFAULT 'pending',
    provider_id TEXT,
    user_id TEXT,
    created DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON public.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_email ON public.orders(email);
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow full access to service_role on orders"
    ON public.orders FOR ALL
    USING (auth.role() = 'service_role');

-- 4. Storage: Create bucket 'user-assets' for audio and PDF files
INSERT INTO storage.buckets (id, name, public)
VALUES ('user-assets', 'user-assets', true)
ON CONFLICT (id) DO UPDATE SET public = true;

CREATE POLICY "Public read for user-assets"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'user-assets');

CREATE POLICY "Service role full access on user-assets"
    ON storage.objects FOR ALL
    USING (bucket_id = 'user-assets' AND auth.role() = 'service_role');
