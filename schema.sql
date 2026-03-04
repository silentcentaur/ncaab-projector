-- ============================================================
-- NCAAB Madness — Supabase Schema
-- Run this in the Supabase SQL Editor to create all tables
-- ============================================================

-- Team season summary stats
CREATE TABLE IF NOT EXISTS team_stats (
    id            SERIAL PRIMARY KEY,
    season        INTEGER NOT NULL,
    team          TEXT NOT NULL,
    conference    TEXT,
    record        TEXT,
    adj_oe        FLOAT,   -- Adjusted Offensive Efficiency
    adj_de        FLOAT,   -- Adjusted Defensive Efficiency
    adj_tempo     FLOAT,   -- Adjusted Tempo
    net_eff       FLOAT,   -- Net Efficiency (adj_oe - adj_de)
    luck          FLOAT,
    sos_oe        FLOAT,
    sos_de        FLOAT,
    ncsos         FLOAT,
    efg_pct       FLOAT,   -- Effective FG%
    tov_pct       FLOAT,   -- Turnover %
    orb_pct       FLOAT,   -- Offensive Rebound %
    ftr           FLOAT,   -- Free Throw Rate
    opp_efg_pct   FLOAT,
    opp_tov_pct   FLOAT,
    opp_orb_pct   FLOAT,
    opp_ftr       FLOAT,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season, team)
);

-- Per-game basic stats
CREATE TABLE IF NOT EXISTS game_history (
    id            SERIAL PRIMARY KEY,
    season        INTEGER NOT NULL,
    game_id       TEXT,
    date          DATE,
    team          TEXT NOT NULL,
    opponent      TEXT,
    venue         TEXT,    -- Home / Away / Neutral
    points_for    INTEGER,
    points_against INTEGER,
    margin        INTEGER,
    result        TEXT,    -- W / L
    tempo         FLOAT,
    possessions   FLOAT,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season, game_id, team)
);

-- Per-game advanced four factors
CREATE TABLE IF NOT EXISTS adv_game_history (
    id            SERIAL PRIMARY KEY,
    season        INTEGER NOT NULL,
    game_id       TEXT,
    date          DATE,
    team          TEXT NOT NULL,
    opponent      TEXT,
    efg_pct       FLOAT,
    tov_pct       FLOAT,
    orb_pct       FLOAT,
    ftr           FLOAT,
    opp_efg_pct   FLOAT,
    opp_tov_pct   FLOAT,
    opp_orb_pct   FLOAT,
    opp_ftr       FLOAT,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season, game_id, team)
);

-- Track when each data type was last refreshed
CREATE TABLE IF NOT EXISTS refresh_log (
    id            SERIAL PRIMARY KEY,
    data_type     TEXT NOT NULL,  -- 'team_stats', 'game_history', 'adv_game_history'
    season        INTEGER NOT NULL,
    rows_upserted INTEGER,
    status        TEXT,           -- 'success' / 'error'
    message       TEXT,
    ran_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast UI queries
CREATE INDEX IF NOT EXISTS idx_team_stats_season    ON team_stats(season);
CREATE INDEX IF NOT EXISTS idx_game_history_team    ON game_history(team, season);
CREATE INDEX IF NOT EXISTS idx_adv_game_history_team ON adv_game_history(team, season);
