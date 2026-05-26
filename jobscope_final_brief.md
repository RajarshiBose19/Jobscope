# JobScope — Personal Job Market Intelligence Tool

## The Problem

Job hunting is blind. I scroll through hundreds of LinkedIn listings, manually read descriptions, guess whether I'm a fit, and apply to too many bad matches. I have no visibility into what the market actually wants, where my gaps are, or whether my search strategy is working. Every decision is made in isolation with no data backing it.

---

## What JobScope Is

A personal job market intelligence tool built on Jetro that has two modes:

1. **A live co-pilot** that sits alongside me while I browse LinkedIn jobs, analyzing each listing in real-time and helping me decide whether to apply or skip.
2. **A historical advisor** that accumulates data from every job I've evaluated and surfaces patterns, trends, and actionable recommendations over time.

It is NOT an auto-applier. It never clicks "Apply" for me. It is a read-only intelligence layer that helps me make better, faster, data-backed decisions about where to spend my effort.

---

## The Workflow

The tool opens LinkedIn, logs in, runs my configured job search with filters, and clicks on the first job listing. It extracts the full job description and sends it to Gemini in a single API call that handles everything: skill extraction, experience parsing, fit scoring, and recommendation generation.

The results get written to DuckDB and the Jetro canvas updates in real-time — showing the live analysis for the current job alongside running statistics from the session. I'm looking at two things: the actual LinkedIn listing in my browser and the Jetro canvas on a second screen (via the Companion App).

Decisions happen through the application itself, similar to how the reference codebase handles it — dialog prompts or terminal input:
- **Apply**: I apply on LinkedIn manually. The tool detects the "Applied" state change on the job card and records it in DuckDB.
- **Skip**: I confirm skip through the application prompt. Recorded in DuckDB, tool moves to the next listing.
- **Bookmark**: Saved to DuckDB for later review.

After each decision, the tool navigates to the next job listing and repeats the cycle. The Jetro canvas refreshes with each new job — the current job analysis updates, and the session statistics (jobs evaluated, average fit score, top skills seen so far) evolve in real-time.

Every evaluation gets stored in DuckDB. This data feeds the historical dashboard that gets sharper over time.

---

## Reference Codebase

The directory `auto_job_applier_linkedIn/` contains an open-source LinkedIn auto job applier. Use this as a reference — NOT as code to copy wholesale. It contains working implementations of:

- **LinkedIn login flow** (`modules/open_chrome.py`, `runAiBot.py` → `login_LN()`) — Selenium-based authentication with retry logic
- **Job search and filter application** (`runAiBot.py` → `apply_filters()`, `set_search_location()`) — how to navigate LinkedIn's search UI and apply filters programmatically
- **Job listing iteration and data extraction** (`runAiBot.py` → `get_job_main_details()`, `get_job_description()`) — extracting job ID, title, company, location, work style, description text, and experience requirements from LinkedIn's DOM
- **Experience parsing with regex** (`runAiBot.py` → `extract_years_of_experience()`) — pattern matching for "3-5 years", "5+ years" etc.
- **AI integration patterns** (`modules/ai/`) — Gemini, OpenAI, and DeepSeek client setup, prompt structures for skill extraction and question answering
- **CSV-based data storage** (`runAiBot.py` → `submitted_jobs()`, `failed_job()`) — how job data is structured and persisted
- **Config architecture** (`config/`) — how user profile, search preferences, and secrets are organized

Study these patterns for how LinkedIn's DOM is structured, what selectors work, how pagination is handled, and how the AI calls are structured. Then write clean, original code for JobScope that does only what we need: navigate, extract, and analyze — never apply.

Key differences from the reference:
- JobScope does NOT fill forms, answer questions, or click Apply
- JobScope writes to DuckDB instead of CSV files
- JobScope's AI calls are for analysis and scoring, not for answering application questions
- JobScope's control flow is driven by the Jetro canvas (Next Job button), not by automatic iteration

---

## Part 1 — Live Dashboard (Real-Time Co-Pilot)

Updates for each job as I browse. Shows me everything I need to make a quick, informed decision:

**Fit Score (0-100)** — Color-coded: green (strong fit), yellow (partial), red (weak). Computed from skills overlap, experience match, and red flag detection.

**Experience Match** — Visual comparison: job asks for X years, I have Y. Shows whether I'm in range, slightly under, or way off.

**Skills Breakdown** — The core visual. Three columns:
- ✅ Matched skills (I have these — the job wants them)
- ❌ Missing required skills (gaps I need to address in my application)
- ⚠️ Missing nice-to-haves (not dealbreakers but worth noting)

**Salary/CTC Check** — If the listing mentions compensation, how does it compare to my expected 12 LPA? Am I in range or wasting my time?

**Red Flags** — Automatic detection of dealbreakers: staffing/recruiting companies, unrealistic experience requirements (10+ years for a mid role), must-have skills completely outside my domain, visa/citizenship requirements I can't meet.

**AI Recommendation** — A nuanced, human-readable take on the role. Not just "good match" but WHY. What to highlight in my application, what gaps to address, whether the role is worth a stretch application.

**Resume Tailoring Suggestions** — For jobs with a decent fit score, specific advice on what to emphasize from my existing experience. "Highlight your Lambda and API Gateway work — this role's microservices focus maps directly to your serverless architecture experience. Downplay MVC, lead with your React + API work." This turns a generic resume into a targeted one without rewriting anything — just reordering emphasis.

**Talking Points Generator** — When I mark a job as "Applied", generate 3-4 specific talking points to weave into my cover letter or bring up in an interview. Not a generic cover letter — sharp, targeted bullets: "Lead with your Bedrock + RAG chatbot project — it maps directly to their 'AI integration experience' requirement. Mention your CloudFormation work when they ask about infrastructure. Your Connect admin UI shows you can build internal tools, which is their core product." This bridges the gap between job evaluation and actually applying well.

**JD Quality Signal** — Rate the job listing itself. A vague description stuffed with buzzwords and no specifics ("fast-paced environment", "rockstar developer") often signals a disorganized hiring process. A well-structured JD with clear requirements, tech stack, and team context signals a company that knows what they want. Quick visual indicator: well-written / average / vague.

**Live Session Stats** — Running counters that update as I move through jobs: total evaluated this session, applied count, skipped count, bookmarked count, average fit score so far, top 5 skills seen this session. This gives me a sense of how the session is going without waiting for the historical dashboard.

### AI Usage in Live Dashboard
One Gemini API call per job. A single prompt that returns: extracted tech stack, extracted soft skills, experience requirement, fit score, recommendation text, resume tailoring suggestion, and JD quality assessment. Everything in one response. No separate calls for extraction and scoring.

---

## Part 2 — Historical Dashboard (Strategy Advisor)

Queries the growing DuckDB dataset after browsing sessions. Shows patterns invisible at the individual job level:

**Skill Gap Ranking** — Across all jobs scraped, which missing skills appear most frequently? Ranked by impact. "Kubernetes appeared in 34 of 80 jobs you were otherwise a fit for. Learning it would unlock 42% more opportunities."

**Skill Adjacency Map** — Don't just show what's missing — show what's closest to what I already know. "You're missing Kubernetes, but you have Docker knowledge and AWS ECS experience, which are directly adjacent. Estimated ramp-up: 2-3 weeks." This turns a gap analysis into a learning plan.

**Search Term Report Card** — Which of my search terms ("ASP.NET Developer", "Full Stack Developer", "AWS Engineer") produce the highest average fit scores? Which ones waste my time? Helps me refine my search strategy with data.

**Fit Score Distribution** — Histogram of all my fit scores. Am I mostly finding green jobs (good targeting) or mostly red (wrong strategy)?

**Market Salary Map** — Salary/CTC distribution across evaluated jobs, broken down by role type, experience level, location. Where does my 12 LPA expectation sit?

**Experience Band Analysis** — What experience ranges are jobs asking for? Am I targeting the right level or consistently reaching too high?

**Company Intelligence** — Which companies post most frequently? Which am I a strong fit for? If a company keeps reposting the same role, flag it — either high turnover or a hard-to-fill position. Both are useful signals.

**Application Funnel** — Jobs evaluated → marked "Will Apply" → actually applied. Tracks my follow-through and shows conversion at each stage.

**Weekly Trends** — Am I seeing more or fewer strong matches over time? Is the market improving or tightening for my profile?

**Interview Prep Seeds** — For jobs I've marked as "Applied", auto-generate likely interview topics based on the JD. "They emphasize distributed systems and event-driven architecture — expect questions about message queues, eventual consistency, and service communication patterns. Your Amazon Connect project is your strongest relevant talking point." This turns job hunting data into interview preparation automatically.

**Learning Priority Recommendations** — The synthesis insight. Cross-reference missing skills with frequency, salary impact, and adjacency to my current skills. "Docker: high demand, easy ramp-up, moderate salary impact. Kubernetes: high demand, moderate ramp-up, high salary impact. TypeScript: moderate demand, easy ramp-up, low salary impact. Recommended priority: Docker → Kubernetes → TypeScript."

**Response Tracking** — A feedback loop that closes the intelligence cycle. After applying, I come back and mark which applications got callbacks, interviews, or rejections. Over time the system identifies what responding companies had in common versus the ones that ghosted. "Companies that responded were mostly mid-size startups looking for full-stack roles. Enterprise companies looking for pure backend specialists never responded. Your callback rate is 3x higher when your fit score was above 75." This becomes the most valuable dataset over time — it tells me not just where to apply, but where I actually have a chance.

### AI Usage in Historical Dashboard
Almost entirely SQL aggregations over DuckDB. One optional AI call per session to generate the learning priority summary, interview prep seeds, and response pattern analysis in natural language.

---

## What Makes This Different

Most job tools are either auto-appliers (spray and pray) or simple trackers (glorified spreadsheets). JobScope is neither.

**It's a decision engine, not an automation tool.** It doesn't remove human judgment — it arms it with data. I still decide. I just decide better.

**It learns my market over time.** Every job I evaluate makes the historical insights sharper. After 200 jobs, I have a personal market research report that no job board provides.

**AI is used where it matters, code handles the rest.** Skills extraction from unstructured JDs needs AI — regex can't understand context. But aggregations, scoring formulas, and trend analysis are pure SQL. This isn't "AI everything" — it's knowing which tool fits which problem.

**It generates actionable output, not just charts.** Resume tailoring suggestions, talking points for applications, interview prep topics, and learning priorities with estimated ramp-up times. These are things I can act on immediately, not just look at.

**It closes the feedback loop.** Most tools stop at "you applied." JobScope tracks what happens after — which applications got responses, which got ghosted, and what the responding companies had in common. This turns job hunting from guesswork into a data-driven feedback cycle.

---

## How Jetro Is Used (Deep Integration Strategy)

Jetro is the intelligence layer that makes raw scraping and AI analysis visible, queryable, and shareable. Here's how each Jetro feature is used with purpose:

### Canvas as Live Intelligence Display
The Jetro canvas shows two views: a **live view** that updates with each job the scraper processes (current job analysis, session stats, running skill trends) and a **historical view** that queries accumulated DuckDB data across all sessions (skill gaps, salary maps, fit distributions, learning recommendations). These are separate canvas layouts that persist and evolve.

The live view refreshes automatically as the scraper writes new data to DuckDB — every time a job is evaluated, the canvas reflects the latest analysis without manual refresh. The historical view is query-driven: all charts and insights are powered by live DuckDB queries, not static snapshots.

### DuckDB as the Central Nervous System
Every piece of data flows through DuckDB. The scraper writes raw job data into it. The AI analysis results get stored in it. My decisions (applied, skipped, bookmarked) get recorded in it. The canvas reads from it. DuckDB is what connects the live session to the historical insights — it's the persistence layer that makes the tool get smarter over time. All canvas visualizations are powered by live DuckDB queries, not static data.

### Companion App for Dual-Screen Workflow
The actual workflow requires two screens: LinkedIn in the browser and the Jetro canvas for analysis. The Companion App mirrors the canvas in real-time to a separate browser tab, tablet, or second monitor. While the scraper iterates through jobs in the browser, I watch the analysis update on the companion screen and make my decision through the application prompts. This is the intended Jetro use case — the agent builds in the editor, the user views via the companion. Changes sync instantly.

### Deploy for Sharing
The historical dashboard — with its skill gap analysis, market insights, and fit distributions — gets deployed as a standalone URL via Jetro's deploy feature. This serves two purposes:
1. For the Berrywise submission: evaluators click a link and interact with a live dashboard populated with real data. No setup, no installation.
2. For personal use: I can check my job market intelligence from any device without opening VS Code.

### Skills for Reusable Workflows
Create a Jetro skill that teaches Claude Code how to build job analysis dashboards from DuckDB data. This means if I want a new visualization or a different slice of the data, I describe it in natural language and Claude Code knows exactly how to query DuckDB and render it on the canvas — because the skill encodes the patterns. This shows understanding of Jetro's ecosystem beyond just "put charts on a canvas."

### Why This Can't Be Replaced by Streamlit/Grafana
A traditional dashboard tool could display the same charts. But it can't:
- Update in real-time as an external scraper writes to a shared DuckDB file
- Mirror to a companion device for a dual-screen workflow without extra infrastructure
- Be iteratively built and modified by an AI agent through natural language
- Deploy individual frames as standalone shareable apps with their own URLs
- Store reusable patterns as skills for future expansion
Jetro isn't just rendering the output — it's the layer that ties the scraper, the AI, the database, and the user's visibility together into a cohesive workflow.

---

## My Profile (Used for Fit Scoring)

```
Name: Rajarshi Bose
Current Role: Full-Stack Developer (Solutions) at Tecnomic Systems, Chennai
Experience: 2+ years (Jan 2024 – Present), promoted within 12 months
Education: B.Tech in Computer Science, VIT Vellore (2020–2024)

Skills:
  Languages & Frameworks: C#, ASP.NET Core (MVC & Web API), React.js, Python, SQL, JavaScript
  Databases: PostgreSQL, DynamoDB, MySQL
  Cloud (AWS): Lambda, API Gateway, S3, RDS, DynamoDB, OpenSearch, CloudFormation
  AI/ML: Amazon Bedrock, RAG Architecture, Prompt Engineering
  Concepts: REST API Design, JWT Auth, Entity Framework Core, Serverless, SPA, Microservices
  Tools: Git, Postman, Visual Studio, VS Code

Certifications (4 active):
  - AWS Solutions Architect – Associate
  - AWS Developer – Associate
  - AWS AI Practitioner
  - AWS Cloud Practitioner

Key Projects:
  - Admin UI for Amazon Connect (ASP.NET Core MVC, React.js, Lambda, API Gateway)
  - Gen AI Chatbot with Bedrock Agents (RAG, Lambda, React.js)
  - Chrome Extension for JS Automation

Location: Bangalore, India (open to Chennai)
Current CTC: 7.5 LPA | Expected CTC: 12 LPA
Notice Period: 60 days
```

---

## Submission Context

This is a Round 2 submission for a Backend Developer role at Berrywise (berrywise.ai) — a portfolio analytics and asset management company in Bangalore. They asked candidates to build something using Jetro that demonstrates deep engagement with the tool and strong technical thinking.

The parallel to Berrywise's own work is deliberate:
- **Berrywise**: Raw financial data → quantitative analysis → scores and ranks investment opportunities → visual intelligence → informed decision-making.
- **JobScope**: Raw job market data → scoring algorithms → ranks opportunities by fit → visual intelligence → informed decision-making.

Same pattern. Different domain. The thinking transfers directly.

What this project demonstrates:
1. **Backend depth** — Data extraction pipeline, AI integration, scoring algorithms, data modelling
2. **Deep Jetro engagement** — Canvas as interactive control surface, DuckDB as central data store, Companion App for dual-screen workflow, Deploy for shareable output, Skills for reusable patterns. Every major Jetro feature is used with purpose.
3. **Intelligent AI usage** — Using AI where it adds genuine value (unstructured text understanding, nuanced recommendations) and code where it's better (aggregations, scoring, trend analysis)
4. **Real problem solving** — This isn't a toy demo. It solves a problem I'm dealing with right now, today.

---

## Open Questions (To Figure Out During Build)

- What's the exact scoring formula? How should experience match, skills overlap, and red flags be weighted?
- How should the single Gemini prompt be structured to return all needed data (extraction + scoring + recommendations) in one call?
- What's the best way to handle jobs where salary/CTC isn't mentioned?
- How should "Bookmark for Later" jobs be resurfaced and re-evaluated?
- What visualization types work best on Jetro's canvas for each metric?
- How does the Python scraper communicate with the Jetro canvas? Options: scraper writes to DuckDB, canvas reads from DuckDB on a refresh interval. Or: scraper triggers canvas updates via Jetro's tools. Need to figure out which approach Jetro supports.
- How to make canvas buttons (Apply/Skip/Bookmark/Next) trigger both DuckDB writes and scraper actions?
- What should the Jetro skill encode? The DuckDB schema? The chart-building patterns? The prompt structure?
- What's the best canvas layout — single canvas with switchable views, or separate canvases for live vs historical?
- Should there be a "company watchlist" feature?
- How to detect the "Applied" state change on LinkedIn reliably?
- What's the deploy URL structure — full historical dashboard or specific frames?
