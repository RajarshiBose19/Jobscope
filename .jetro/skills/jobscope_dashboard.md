---
name: JobScope Dashboard
description: Build job-analysis dashboards from the JobScope DuckDB at projects/jobscope/jobscope.duckdb. Covers schema, canonical views, and idiomatic frame patterns.
---

# JobScope Dashboard Skill

Use this when the user asks for any new chart/table/insight derived from their
JobScope evaluation data. The DB lives at `projects/jobscope/jobscope.duckdb`.

## Tables (canonical)

- `jobs` — one row per LinkedIn job scraped
- `analyses` — one row per Gemini analysis, versioned by `prompt_version`
- `job_skills(job_id, skill_canonical, skill_as_written, kind)` — `kind ∈ {required, nice_to_have}`
- `skills_canonical(skill_canonical, display_name, category, aliases)`
- `user_skills(skill_canonical, proficiency, years)` — the candidate's profile
- `user_profile` — single row with name, experience, ctc
- `decisions(job_id, session_id, decided_at, decision, source)` — event-sourced; `decision ∈ {apply, skip, bookmark}`
- `sessions(session_id, started_at, ended_at, search_terms, ...)`
- `session_state` — single row pointer to current session/job

## Views you should prefer over base tables

- `v_job_analysis` — jobs JOIN latest analysis + latest decision (use this for per-job rendering)
- `v_skill_gaps` — required skills NOT in user_skills, ranked by frequency
- `v_search_term_report` — per-search-term jobs_seen, avg_fit, apply_rate
- `v_current_session_stats` — live KPIs scoped to the active session

## Conventions

- Always open the DB **read-only** in refresh scripts: `duckdb.connect(path, read_only=True)`.
- Refresh scripts live in `.jetro/scripts/`. They print JSON to stdout. The
  JSON is delivered to the bound frame via `jet:refresh` CustomEvent (NOT
  `message`). Read it as `e.detail`.
- Frames go in `.jetro/frames/<name>.html`. Use Plotly via `<script src>` (CDN
  shimmed locally by Jetro). NEVER inline Plotly source.
- Refresh interval ≥ 30s for historical aggregates; ≥ 5s for live KPIs.

## Common patterns

### "Top N most-asked skills"
```sql
SELECT display_name, jobs_asking
FROM v_skill_gaps
ORDER BY jobs_asking DESC LIMIT 20;
```

### "My response/apply rate by company size or sector"
Not in MVP schema. Requires extending `jobs` with a `sector` column or joining
a future `companies` table.

### "Best fit unrated jobs (need decision)"
```sql
SELECT title, company, fit_score, recommendation
FROM v_job_analysis
WHERE latest_decision IS NULL AND fit_score >= 70
ORDER BY fit_score DESC LIMIT 25;
```

## Anti-patterns

- Do NOT write `jobs` directly without `v_job_analysis` when you also want fit data
- Do NOT compute matched/missing client-side; always join `job_skills` against
  `user_skills` in SQL
- Do NOT bind a Python refresh script to a frame that already subscribes to a
  C2 wire — pick one mechanism per frame
