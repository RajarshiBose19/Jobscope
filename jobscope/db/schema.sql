-- jobscope schema v1. Requires duckdb >= 1.0.

CREATE TABLE IF NOT EXISTS jobs (
  job_id            VARCHAR PRIMARY KEY,
  session_id        VARCHAR NOT NULL,
  scraped_at        TIMESTAMPTZ NOT NULL,
  search_term       VARCHAR,
  title             VARCHAR,
  company           VARCHAR,
  location          VARCHAR,
  work_style        VARCHAR,
  posted_relative   VARCHAR,
  experience_text   VARCHAR,
  experience_min    INTEGER,
  experience_max    INTEGER,
  salary_min_lpa    DOUBLE,
  salary_max_lpa    DOUBLE,
  salary_text       VARCHAR,
  jd_full_text      TEXT,
  jd_url            VARCHAR,
  analysis_status   VARCHAR NOT NULL DEFAULT 'pending',
  analysis_error    VARCHAR
);

CREATE TABLE IF NOT EXISTS analyses (
  analysis_id        VARCHAR PRIMARY KEY,
  job_id             VARCHAR NOT NULL,
  prompt_version     VARCHAR NOT NULL,
  model_name         VARCHAR NOT NULL,
  analyzed_at        TIMESTAMPTZ NOT NULL,
  latency_ms         INTEGER,
  fit_score          INTEGER,
  experience_verdict VARCHAR,
  jd_quality         VARCHAR,
  red_flags          JSON,
  recommendation     TEXT,
  resume_tailoring   TEXT,
  raw_response       JSON
);

CREATE TABLE IF NOT EXISTS job_skills (
  job_id            VARCHAR NOT NULL,
  skill_canonical   VARCHAR NOT NULL,
  skill_as_written  VARCHAR NOT NULL,
  kind              VARCHAR NOT NULL,
  PRIMARY KEY (job_id, skill_canonical, kind)
);

CREATE TABLE IF NOT EXISTS skills_canonical (
  skill_canonical   VARCHAR PRIMARY KEY,
  display_name      VARCHAR NOT NULL,
  category          VARCHAR,
  aliases           JSON
);

CREATE TABLE IF NOT EXISTS user_skills (
  skill_canonical   VARCHAR PRIMARY KEY,
  proficiency       VARCHAR,
  years             DOUBLE
);

CREATE TABLE IF NOT EXISTS user_profile (
  id                INTEGER PRIMARY KEY,
  full_name         VARCHAR,
  current_role      VARCHAR,
  current_company   VARCHAR,
  experience_years  DOUBLE,
  current_ctc_lpa   DOUBLE,
  expected_ctc_lpa  DOUBLE,
  current_location  VARCHAR,
  willing_locations JSON,
  certifications    JSON,
  updated_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS decisions (
  decision_id       VARCHAR PRIMARY KEY,
  job_id            VARCHAR NOT NULL,
  session_id        VARCHAR NOT NULL,
  decided_at        TIMESTAMPTZ NOT NULL,
  decision          VARCHAR NOT NULL,
  source            VARCHAR NOT NULL,
  notes             TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id        VARCHAR PRIMARY KEY,
  started_at        TIMESTAMPTZ NOT NULL,
  ended_at          TIMESTAMPTZ,
  search_terms      JSON,
  search_location   VARCHAR,
  filters_applied   JSON,
  ended_reason      VARCHAR
);

CREATE TABLE IF NOT EXISTS session_state (
  id                INTEGER PRIMARY KEY,
  current_session_id VARCHAR,
  current_job_id    VARCHAR,
  last_active_at    TIMESTAMPTZ
);

INSERT OR IGNORE INTO session_state(id) VALUES (1);
