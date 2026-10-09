---
name: joe-outreach
description: Automated daily lead generation, email permuting (first.last, f.last, etc.), thread-aware deduplication, resume variant routing, and outreach for Joseph Heupler with resume attachment.
---

# Joe Outreach & Recruiter Sourcing Skill (`joe-outreach`)

Automates discovering prospective engineering leads/recruiters, checking thread conversation reply history and deduplication ledger, dynamically selecting the best resume variant, and sending tailored referral pitches for Joseph Heupler with his resume attached.

## 1. Candidate Context
- **Candidate:** Joseph Heupler (`jheupler@berkeley.edu`)
- **LinkedIn:** `https://www.linkedin.com/in/joseph-heupler/` | **Portfolio:** `josephheupler.com`
- **Education:** UC Berkeley (Data Science & Cognitive Science)
- **Strengths:** Production AI Agents (LangGraph, GraphRAG with 96% grounded eval), Data Platform (dbt/Airflow, 100k+ invoices), Full Stack (Python, TypeScript, React, FastAPI).

## 2. Dynamic Resume Variant Routing
Select the tailored resume matching the recruiter's exact role:
- **General / Agentic AI / Default:** `/Users/mlubich/dev/resumes/resumes/resume_joseph_heupler/resume_joseph_heupler.pdf`
- **Data Science / ML / AI Research:** `/Users/mlubich/dev/resumes/resumes/resume_joseph_heupler_ds/resume_joseph_heupler_ds.pdf`
- **Software Engineering / Full-Stack / Backend / Frontend:** `/Users/mlubich/dev/resumes/resumes/resume_joseph_heupler_swe/resume_joseph_heupler_swe.pdf`
- **IT / Cloud Systems / Support / Infrastructure:** `/Users/mlubich/dev/resumes/resumes/resume_joseph_heupler_it/resume_joseph_heupler_it.pdf`

## 3. Strict Safeguards & Exclusions
- **Job Opportunities Only**: Strictly exclude all networking events, webinars, marketing digests, and non-job outreach.
- **NEVER CONTACT:** Perry Barrow (W3Sourcing).
- **NEVER REFER TO JOE (Kept for Misha):**
  - **Mach Industries**
  - **Anduril**
  - **EchoStar / Dish**
  - **AMD**
- **Thread-Aware Deduplication:**
  - Before emailing or drafting, check both the conversation thread history in Mail.app (messages where we already replied) AND the deduplication ledger (`~/.config/joe-referral/ledger.json`).
  - If a thread or recruiter was already emailed or contacted, **NEVER DOUBLE-MESSAGE**.

## 4. Dispatch Format
- **From:** `michaelle.lubich@gmail.com`
- **CC:** `jheupler@berkeley.edu`
- **Attachment:** Tailored resume PDF for the role
- **Sign-off:** "resume attached, more at josephheupler.com. misha"
