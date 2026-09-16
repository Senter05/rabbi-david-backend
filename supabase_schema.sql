-- Supabase SQL Schema for Rabbi David (https://rabbidavid.org)
-- Run this script in the Supabase SQL Editor to set up tables, RLS policies, and private storage.

-- 1. Profiles Table (extends auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- 2. User Readings Table
CREATE TABLE IF NOT EXISTS public.user_readings (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft',
    tier TEXT NOT NULL DEFAULT 'free',
    title TEXT,
    answers JSONB DEFAULT '{}'::jsonb,
    reading JSONB,
    plan JSONB,
    voice JSONB,
    completed_days JSONB DEFAULT '[]'::jsonb,
    audio_file TEXT,
    intro_file TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_readings_user_id ON public.user_readings(user_id);
ALTER TABLE public.user_readings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own readings"
    ON public.user_readings FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own readings"
    ON public.user_readings FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own readings"
    ON public.user_readings FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own readings"
    ON public.user_readings FOR DELETE
    USING (auth.uid() = user_id);

-- 3. User Orders Table
CREATE TABLE IF NOT EXISTS public.user_orders (
    id TEXT PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    session_id TEXT,
    email TEXT NOT NULL,
    book_id TEXT,
    amount INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'usd',
    delivery_status TEXT DEFAULT 'pending',
    provider_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_orders_user_id ON public.user_orders(user_id);
ALTER TABLE public.user_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own orders"
    ON public.user_orders FOR SELECT
    USING (auth.uid() = user_id);

-- 4. Trigger for Automatic Profile Creation on Signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name, email_verified, created_at, updated_at)
    VALUES (
        new.id,
        new.email,
        COALESCE(new.raw_user_meta_data->>'name', ''),
        COALESCE(new.email_confirmed_at IS NOT NULL, FALSE),
        now(),
        now()
    )
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        name = EXCLUDED.name,
        updated_at = now();
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 5. Storage: Create private bucket 'user-assets' if it does not exist
INSERT INTO storage.buckets (id, name, public)
VALUES ('user-assets', 'user-assets', false)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Users can read own assets"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'user-assets' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can upload own assets"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'user-assets' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can update own assets"
    ON storage.objects FOR UPDATE
    USING (bucket_id = 'user-assets' AND auth.uid()::text = (storage.foldername(name))[1]);
