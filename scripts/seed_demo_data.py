"""One-shot: seed ~20 realistic synthetic jobs+analyses+decisions for canvas demo.

Run once:  .venv/Scripts/python.exe scripts/seed_demo_data.py
Wipe with: python -m jobscope reset --confirm
"""
import random
from datetime import datetime, timezone, timedelta
from jobscope.db.connection import open_rw, init_schema
from jobscope.db import repo
from jobscope import config

random.seed(42)
conn = open_rw(config.DB_PATH)
init_schema(conn)

sid = repo.start_session(conn, config.SEARCH_TERMS, config.SEARCH_LOCATION, {"demo": True})

# (term, title, company, location, work_style, fit, skills, smin, smax, red_flags)
JOBS = [
    ("AWS Engineer", "Senior AWS Engineer", "Cloudwave", "Bangalore", "Hybrid", 82,
     [("aws-lambda","required"),("aws-api-gateway","required"),("python","required"),("terraform","required")], 14.0, 22.0, []),
    ("AWS Engineer", "Cloud Infrastructure Engineer", "Razorpay", "Bangalore", "On-site", 71,
     [("aws","required"),("terraform","required"),("kubernetes","required"),("docker","required")], 18.0, 28.0, []),
    ("AWS Engineer", "AWS DevOps Engineer", "TalentBridge Solutions", "Bangalore", "Remote", 35,
     [("kubernetes","required"),("jenkins","required"),("ansible","required"),("helm","required")], None, None,
     [("staffing_recruiting","Talent agency reposting roles")]),
    ("AWS Engineer", "Backend Engineer (AWS focus)", "Acko", "Bangalore", "Hybrid", 76,
     [("aws-lambda","required"),("python","required"),("postgresql","required"),("aws-ecs","required")], 16.0, 24.0, []),
    ("Full Stack Developer", "Full Stack Engineer", "Zerodha", "Bangalore", "On-site", 68,
     [("react","required"),("nodejs","required"),("postgresql","required"),("kubernetes","required")], 18.0, 30.0, []),
    ("Full Stack Developer", "Senior Full Stack Developer", "CRED", "Bangalore", "Hybrid", 74,
     [("react","required"),("python","required"),("aws","required"),("django","required")], 22.0, 35.0, []),
    ("Full Stack Developer", "MERN Stack Developer", "Generic Staffing Co", "Bangalore", "On-site", 28,
     [("react","required"),("nodejs","required"),("mongodb","required"),("express","required")], 6.0, 10.0,
     [("staffing_recruiting","Staffing firm"),("salary_below_expected","Below expected CTC")]),
    ("Full Stack Developer", "Full Stack (.NET + React)", "Tata Digital", "Bangalore", "Hybrid", 88,
     [("csharp","required"),("aspnet-core","required"),("react","required"),("sql","required")], 13.0, 20.0, []),
    ("ASP.NET Developer", "Senior .NET Developer", "Infosys", "Bangalore", "On-site", 79,
     [("csharp","required"),("aspnet-core","required"),("sqlserver","required"),("ef-core","required")], 12.0, 18.0, []),
    ("ASP.NET Developer", ".NET Core Backend", "Wipro Digital", "Bangalore", "Hybrid", 72,
     [("csharp","required"),("aspnet-core","required"),("azure","required"),("sql","required")], 14.0, 22.0, []),
    ("ASP.NET Developer", "Full Stack .NET Engineer", "Tecnomic Systems", "Chennai", "Hybrid", 91,
     [("csharp","required"),("aspnet-core","required"),("react","required"),("aws-lambda","required")], 12.0, 16.0, []),
    ("Software Developer", "Backend Engineer", "Swiggy", "Bangalore", "Hybrid", 64,
     [("java","required"),("spring-boot","required"),("kafka","required"),("postgresql","required")], 24.0, 36.0, []),
    ("Software Developer", "Software Engineer II", "Flipkart", "Bangalore", "Hybrid", 58,
     [("java","required"),("kubernetes","required"),("kafka","required"),("redis","required")], 22.0, 32.0, []),
    ("Software Developer", "Senior Software Engineer", "Atlassian", "Bangalore", "Remote", 45,
     [("java","required"),("kubernetes","required"),("aws","required"),("graphql","required"),("rust","required")], 35.0, 55.0,
     [("experience_mismatch","Asking 7+ years")]),
    ("AI Engineer", "AI/ML Engineer", "Pixxel", "Bangalore", "On-site", 81,
     [("python","required"),("bedrock","required"),("rag","required"),("aws-lambda","required")], 18.0, 28.0, []),
    ("AI Engineer", "Gen AI Engineer", "Sprinklr", "Bangalore", "Hybrid", 77,
     [("python","required"),("langchain","required"),("rag","required"),("openai-api","required")], 20.0, 32.0, []),
    ("AI Engineer", "LLM Application Engineer", "Glean", "Bangalore", "On-site", 52,
     [("python","required"),("kubernetes","required"),("rust","required"),("langchain","required"),("terraform","required")], 30.0, 50.0,
     [("skill_domain_mismatch","Heavy infra/Rust focus")]),
    ("AI Engineer", "AI Solutions Engineer (Junior)", "Innovate Hire LLC", "Remote", "Remote", 22,
     [("python","required"),("kubernetes","required"),("docker","required"),("aws","required")], None, None,
     [("staffing_recruiting","Recruiting firm"),("vague_jd","No concrete stack")]),
    ("Full Stack Developer", "Full Stack Web Developer", "Razorpay", "Bangalore", "Hybrid", 70,
     [("react","required"),("python","required"),("postgresql","required"),("graphql","required")], 16.0, 24.0, []),
    ("AWS Engineer", "Solutions Architect Associate", "Capgemini", "Bangalore", "On-site", 65,
     [("aws","required"),("aws-cloudformation","required"),("python","required"),("docker","required")], 10.0, 15.0, []),
]

base_ts = datetime.now(timezone.utc) - timedelta(hours=2)

for i, (term, title, company, location, work_style, fit, skills, smin, smax, red_flags) in enumerate(JOBS, start=1):
    jid = f"demo-{i:04d}"
    scraped = base_ts + timedelta(minutes=i * 4)
    repo.upsert_job(conn, {
        "job_id": jid, "session_id": sid, "scraped_at": scraped,
        "search_term": term, "title": title, "company": company, "location": location,
        "work_style": work_style, "posted_relative": "1 day ago",
        "experience_text": None, "experience_min": 2, "experience_max": 5,
        "salary_min_lpa": smin, "salary_max_lpa": smax, "salary_text": None,
        "jd_full_text": f"Demo JD for {title} at {company}",
        "jd_url": f"https://www.linkedin.com/jobs/view/{jid}/",
    })
    repo.replace_job_skills(conn, jid, [
        {"canonical": c, "as_written": c.replace("-", " ").title(), "kind": k}
        for c, k in skills
    ])
    if fit >= 75:
        rec_word = "Strong"
        verdict = "in_range"
        quality = "well_written"
    elif fit >= 60:
        rec_word = "Decent"
        verdict = "in_range"
        quality = "average"
    elif fit >= 40:
        rec_word = "Marginal"
        verdict = "under"
        quality = "average"
    else:
        rec_word = "Weak"
        verdict = "over"
        quality = "vague"
    repo.insert_analysis(conn,
        job_id=jid, prompt_version="1.0.0", model_name="gemini-2.5-flash-lite",
        latency_ms=random.randint(2000, 4500),
        parsed={
            "fit_score": fit,
            "experience_verdict": verdict,
            "jd_quality": quality,
            "red_flags": [{"kind": k, "text": t} for k, t in red_flags],
            "recommendation": f"{rec_word} fit. Tech stack overlap is the main signal.",
            "resume_tailoring": "Lead with the Gen AI Chatbot project and Admin UI for Amazon Connect.",
        },
        raw_json="{}",
    )
    repo.mark_job_status(conn, jid, "analyzed")
    decision = "apply" if fit >= 70 else ("bookmark" if fit >= 50 else "skip")
    repo.record_decision(conn, job_id=jid, session_id=sid, decision=decision, source="user")

conn.close()
print(f"Seeded {len(JOBS)} jobs with analyses + decisions across {len(set(j[0] for j in JOBS))} search terms.")
