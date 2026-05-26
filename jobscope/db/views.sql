CREATE OR REPLACE VIEW v_job_analysis AS
SELECT j.*,
       a.analysis_id, a.fit_score, a.experience_verdict, a.jd_quality,
       a.red_flags, a.recommendation, a.resume_tailoring, a.analyzed_at, a.model_name,
       (SELECT LIST(decision ORDER BY decided_at DESC)
          FROM decisions d WHERE d.job_id = j.job_id) AS decision_history,
       (SELECT decision FROM decisions d
          WHERE d.job_id = j.job_id ORDER BY d.decided_at DESC LIMIT 1) AS latest_decision
FROM jobs j
LEFT JOIN (
  SELECT * FROM analyses
  QUALIFY ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY analyzed_at DESC) = 1
) a USING (job_id);

CREATE OR REPLACE VIEW v_skill_gaps AS
SELECT js.skill_canonical,
       COALESCE(sc.display_name, js.skill_canonical) AS display_name,
       COUNT(DISTINCT js.job_id) AS jobs_asking,
       COUNT(DISTINCT js.job_id) FILTER (
         WHERE js.skill_canonical NOT IN (SELECT skill_canonical FROM user_skills)
       ) AS jobs_where_missing,
       AVG(a.fit_score) AS avg_fit_when_asked
FROM job_skills js
LEFT JOIN skills_canonical sc USING (skill_canonical)
LEFT JOIN v_job_analysis a USING (job_id)
WHERE js.kind = 'required'
GROUP BY js.skill_canonical, COALESCE(sc.display_name, js.skill_canonical)
ORDER BY jobs_where_missing DESC;

CREATE OR REPLACE VIEW v_search_term_report AS
SELECT j.search_term,
       COUNT(*) AS jobs_seen,
       ROUND(AVG(a.fit_score), 1) AS avg_fit,
       COUNT(*) FILTER (WHERE d.decision = 'apply')  AS applied,
       COUNT(*) FILTER (WHERE d.decision = 'skip')   AS skipped,
       ROUND(100.0 * COUNT(*) FILTER (WHERE d.decision = 'apply')
             / NULLIF(COUNT(*), 0), 1) AS apply_rate_pct
FROM jobs j
LEFT JOIN v_job_analysis a USING (job_id)
LEFT JOIN LATERAL (
  SELECT decision FROM decisions
  WHERE job_id = j.job_id ORDER BY decided_at DESC LIMIT 1
) d ON true
GROUP BY j.search_term
ORDER BY avg_fit DESC NULLS LAST;

CREATE OR REPLACE VIEW v_current_session_stats AS
SELECT s.session_id, s.started_at,
       COUNT(DISTINCT j.job_id) AS jobs_evaluated,
       COUNT(DISTINCT d.job_id) FILTER (WHERE d.decision='apply')    AS applied,
       COUNT(DISTINCT d.job_id) FILTER (WHERE d.decision='skip')     AS skipped,
       COUNT(DISTINCT d.job_id) FILTER (WHERE d.decision='bookmark') AS bookmarked,
       ROUND(AVG(a.fit_score), 1) AS avg_fit
FROM sessions s
LEFT JOIN jobs j USING (session_id)
LEFT JOIN decisions d USING (session_id)
LEFT JOIN v_job_analysis a ON a.job_id = j.job_id
WHERE s.session_id = (SELECT current_session_id FROM session_state WHERE id=1)
GROUP BY s.session_id, s.started_at;
