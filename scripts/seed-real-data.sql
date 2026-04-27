-- ============================================================================
-- seed-real-data.sql
-- The Fit Clinic — Replace demo data with real trainers + packages
-- Run against Neon Postgres: psql "$DATABASE_URL" -f scripts/seed-real-data.sql
-- ============================================================================
-- WARNING: This TRUNCATES all tables. Only run once before the Notion → Neon
-- sync populates real clients. After real clients exist, do NOT re-run this.
-- ============================================================================

BEGIN;

-- Clear all demo/seed data
TRUNCATE
  check_ins,
  appointments,
  availability_slots,
  sessions,
  client_packages,
  clients,
  packages,
  trainers,
  app_config
RESTART IDENTITY CASCADE;

-- ─── Real Trainers ──────────────────────────────────────────────────────────
-- Source: Notion Staff Directory (collection://a80c6087-5927-4fda-9ac5-94c73d4921a8)
-- Only inserting currently ACTIVE staff. Terminated staff omitted.

INSERT INTO trainers (external_id, name, email, specialty, avatar_initials) VALUES
  ('notion-mike-shmakov',    'Mike Shmakov',  'mike@fitclinic.io',  'Owner / Head Trainer',          'MS'),
  ('notion-dom-cole',        'Dom Cole',      'dom@fitclinic.io',   'Personal Training',             'DC'),
  ('notion-marie-goulart',   'Marie Goulart', 'marie@fitclinic.io', 'Admin',                         'MG');

-- Note: Add future hires here as they onboard. Match external_id to their
-- Notion Staff Directory page ID for cross-referencing.

-- ─── Package Templates ──────────────────────────────────────────────────────
-- Source: Stripe products (prod_UE8pZpgmnM0mJe = Personal Training)
-- These are the session-count tiers. Pricing lives in Stripe, not here.
-- The Neon DB only tracks session counts for balance/check-in logic.

INSERT INTO packages (name, session_count, description) VALUES
  -- Personal Training tiers (from Stripe)
  ('Personal Training — 12 Sessions',  12, '12 one-on-one 60-min sessions (~6 weeks at 2x/week)'),
  ('Personal Training — 24 Sessions',  24, '24 one-on-one 60-min sessions (~12 weeks at 2x/week)'),
  ('Personal Training — 36 Sessions',  36, '36 one-on-one 60-min sessions (~12 weeks at 3x/week)'),
  ('Personal Training — 48 Sessions',  48, '48 one-on-one 60-min sessions (~16 weeks at 3x/week)'),
  ('Personal Training — 60 Sessions',  60, '60 one-on-one 60-min sessions (~20 weeks at 3x/week)'),
  ('Personal Training — 72 Sessions',  72, '72 one-on-one 60-min sessions (~24 weeks at 3x/week)'),
  ('Personal Training — 96 Sessions',  96, '96 one-on-one 60-min sessions (~32 weeks at 3x/week)'),

  -- 6-Week Starter packages (first-time clients)
  ('6-Week Starter — Bronze',   6,  '6 sessions (1x/week for 6 weeks). First-time clients only.'),
  ('6-Week Starter — Silver',  12,  '12 sessions (2x/week for 6 weeks). First-time clients only.'),
  ('6-Week Starter — Gold',    18,  '18 sessions (3x/week for 6 weeks). First-time clients only.'),

  -- Recovery packages
  ('Recovery 10-Pack',  10, '10 recovery sessions (Graston, cupping, mobility)'),
  ('Recovery 20-Pack',  20, '20 recovery sessions (Graston, cupping, mobility)'),

  -- Coaching (not yet in Stripe as session-based, but track as package for check-in)
  ('Premium Coaching — Weekly', 99, 'Ongoing weekly coaching. 99 = unlimited/recurring marker.');

-- ─── App Config ─────────────────────────────────────────────────────────────
-- Store metadata the app might need

INSERT INTO app_config (key, value) VALUES
  ('gym_name', 'The Fit Clinic'),
  ('gym_location', 'Campbell, CA'),
  ('checkin_domain', 'app.fitclinic.io'),
  ('stripe_product_personal_training', 'prod_UE8pZpgmnM0mJe'),
  ('seed_version', '2026-04-09');

COMMIT;

-- ============================================================================
-- After running this, your next step is:
--   npx tsx scripts/sync-from-notion.ts
-- That will populate the `clients` and `client_packages` tables with real data.
-- ============================================================================
