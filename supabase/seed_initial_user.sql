-- =====================================================================
-- ARIA — Seed the initial user (manual template, NOT run by migrations)
-- =====================================================================
-- Credentials come from environment variables. The script refuses to run
-- when they are unset, empty, or a known weak default.
--
-- Requirements: psql 15+ (for \getenv).
--
-- Usage:
--   export SEED_USER_EMAIL="you@example.com"
--   export SEED_USER_PASSWORD="<a strong password (12+ characters)>"
--   psql "$SUPABASE_DB_URL" -X -f supabase/seed_initial_user.sql
-- =====================================================================
\set ON_ERROR_STOP on

-- Read the credentials from the environment (psql 15+). A missing environment
-- variable leaves the psql variable unset.
\getenv SEED_USER_EMAIL SEED_USER_EMAIL
\getenv SEED_USER_PASSWORD SEED_USER_PASSWORD

-- Abort if SEED_USER_EMAIL is unset or empty.
\if :{?SEED_USER_EMAIL}
\else
\echo 'ERROR: SEED_USER_EMAIL is not set (e.g. SEED_USER_EMAIL=you@example.com)'
\quit
\endif
-- Abort if SEED_USER_PASSWORD is unset or empty.
\if :{?SEED_USER_PASSWORD}
\else
\echo 'ERROR: SEED_USER_PASSWORD is not set (use 12+ characters).'
\quit
\endif

-- Evaluate the empty/weak checks as booleans so \if receives a plain true/false
-- value (psql 15 does not support comparison expressions in \if).
SELECT :'SEED_USER_EMAIL' = ''     AS seed_email_empty,
       :'SEED_USER_PASSWORD' = ''  AS seed_password_empty,
       :'SEED_USER_PASSWORD' = 'admin'    AS seed_password_admin,
       :'SEED_USER_PASSWORD' = 'admin123' AS seed_password_admin123,
       :'SEED_USER_PASSWORD' = 'password' AS seed_password_password
\gset

\if :seed_email_empty
\echo 'ERROR: SEED_USER_EMAIL is empty.'
\quit
\endif

-- Refuse known weak defaults.
\if :seed_password_empty
\echo 'ERROR: SEED_USER_PASSWORD is empty.'
\quit
\endif
\if :seed_password_admin
\echo 'ERROR: SEED_USER_PASSWORD is a known weak default ("admin"). Use 12+ characters.'
\quit
\endif
\if :seed_password_admin123
\echo 'ERROR: SEED_USER_PASSWORD is a known weak default ("admin123"). Use 12+ characters.'
\quit
\endif
\if :seed_password_password
\echo 'ERROR: SEED_USER_PASSWORD is a known weak default ("password"). Use 12+ characters.'
\quit
\endif

-- psql does not interpolate :'VAR' inside dollar-quoted DO blocks, so pass the
-- values through session settings first and read them with current_setting().
SELECT set_config('aria.seed_email', :'SEED_USER_EMAIL', false);
SELECT set_config('aria.seed_password', :'SEED_USER_PASSWORD', false);

DO $$
DECLARE
  v_uid uuid;
  v_email text := current_setting('aria.seed_email');
  v_password text := current_setting('aria.seed_password');
BEGIN
  -- Extra guard: reject short passwords outright.
  IF length(v_password) < 12 THEN
    RAISE EXCEPTION 'SEED_USER_PASSWORD must be at least 12 characters (got %).',
      length(v_password);
  END IF;

  -- Insert the auth user only if the email does not already exist.
  INSERT INTO auth.users (
    instance_id,
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    raw_user_meta_data,
    created_at,
    updated_at,
    confirmation_token,
    email_change,
    email_change_token_new,
    recovery_token
  ) VALUES (
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    v_email,
    crypt(v_password, gen_salt('bf')),
    now(),
    jsonb_build_object('name', split_part(v_email, '@', 1)),
    now(),
    now(),
    '', '', '', ''
  )
  ON CONFLICT DO NOTHING;

  -- Resolve the real UID regardless of whether INSERT ran or was skipped.
  SELECT id INTO v_uid FROM auth.users WHERE email = v_email;

  -- Ensure a public.users row exists (the trigger may already have created it).
  INSERT INTO public.users (id, name, timezone)
  VALUES (v_uid, split_part(v_email, '@', 1), 'UTC')
  ON CONFLICT (id) DO NOTHING;

  -- Ensure the Personal project exists.
  IF NOT EXISTS (
    SELECT 1 FROM public.projects WHERE user_id = v_uid AND name = 'Personal'
  ) THEN
    INSERT INTO public.projects (user_id, name, color, context, is_active)
    VALUES (v_uid, 'Personal', '#6366f1', 'Personal tasks and reminders', true);
  END IF;
END $$;
