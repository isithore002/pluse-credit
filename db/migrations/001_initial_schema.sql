-- PulseCredit Database Schema - Supabase PostgreSQL
-- Deploy to Supabase: copy and paste into SQL Editor

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- profiles: one row per scored user
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  archetype TEXT CHECK (archetype IN ('student','gig_worker','salaried','irregular')),
  created_at TIMESTAMPTZ DEFAULT now(),
  is_demo BOOLEAN DEFAULT false
);

CREATE INDEX idx_profiles_archetype ON profiles(archetype);
CREATE INDEX idx_profiles_is_demo ON profiles(is_demo);

-- transactions: raw parsed UPI data
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  txn_date DATE NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  direction TEXT CHECK (direction IN ('CR','DR')),
  vpa TEXT,
  merchant_name TEXT,
  category TEXT,
  remarks TEXT,
  utr TEXT
);

CREATE INDEX idx_transactions_profile_id ON transactions(profile_id);
CREATE INDEX idx_transactions_txn_date ON transactions(txn_date);

-- feature_vectors: computed dimensions per profile
CREATE TABLE feature_vectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
  computed_at TIMESTAMPTZ DEFAULT now(),
  rhythm_score NUMERIC(5,2),
  merchant_score NUMERIC(5,2),
  social_score NUMERIC(5,2),
  calendar_score NUMERIC(5,2),
  velocity_score NUMERIC(5,2),
  nlp_score NUMERIC(5,2),
  raw_features JSONB
);

CREATE INDEX idx_feature_vectors_profile_id ON feature_vectors(profile_id);

-- scores: final credit score per profile
CREATE TABLE scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
  scored_at TIMESTAMPTZ DEFAULT now(),
  pulse_score INTEGER CHECK (pulse_score BETWEEN 300 AND 850),
  confidence_low INTEGER,
  confidence_high INTEGER,
  xgb_score NUMERIC(5,2),
  ae_reconstruction_error NUMERIC(8,4),
  shap_values JSONB,
  explanation TEXT,
  actions JSONB,
  lender_memo TEXT
);

CREATE INDEX idx_scores_profile_id ON scores(profile_id);
CREATE INDEX idx_scores_pulse_score ON scores(pulse_score);

-- Row-level security (optional but recommended)
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_vectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
