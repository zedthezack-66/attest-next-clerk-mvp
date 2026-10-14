# Attest ATS — Phase 1 backend (FastAPI)

AI-assisted applicant tracking with ZAQA/ZQF-aligned credential verification. This lives in
`apps/api` alongside the existing Next.js MVP (`apps/web`); the dashboard can call it over REST.

## Run locally (no Docker needed)

```bash
py -3.12 -m venv apps/api/.venv
apps/api/.venv/Scripts/python -m pip install -r apps/api/requirements.txt

# SQLite + local disk storage for development
$env:DATABASE_URL = "sqlite:///./attest-dev.db"   # PowerShell
apps/api/.venv/Scripts/python -m uvicorn apps.api.main:app --reload
```

Open http://localhost:8000/docs. Seed login: `manager@attest.local` / `password123` (override with
`SEED_MANAGER_PASSWORD`). For Postgres + pgvector use `infra/docker-compose.yml`, set
`AUTO_CREATE_SCHEMA=false`, and run `alembic -c migrations/alembic.ini upgrade head` from `packages/db-schema`.

Tests (SQLite, end to end): `apps/api/.venv/Scripts/python -m pytest`

Score a candidate without any database:

```bash
apps/api/.venv/Scripts/python -m apps.api.scripts.score_candidate --job apps/api/tests/fixtures/finance_officer_job.json --cv apps/api/tests/fixtures/cv_mwila.txt --cover-letter apps/api/tests/fixtures/cover_mwila.txt
```

## Pipeline

```
POST /applications/submit ──► store files ──► PipelineJob(process_application) ──► BackgroundTask
                                                                   │  (workers/pipeline_worker.py drains retries)
                                                                   ▼
  extract text (PDF / DOCX / TXT / image OCR*) ──► parse CV (LLM if configured, else heuristics)
      ──► verify each award vs institution registry + ZQF ──► qualifications rows
      ──► candidate profile + cover-letter summary ──► fit score ──► audit log
```

\* Image OCR runs only if `pytesseract` + the tesseract binary are installed; otherwise the document is
stored and an `document.text_unavailable` audit event is recorded.

**The LLM only extracts.** ZQF levels, registry verification and scoring are deterministic code, so a
model hallucination can never mark a degree as verified. LLM output is schema-validated and falls back
to the heuristic parser on any failure.

## Data model (new / changed)

| Table | Purpose |
|---|---|
| `users` | + `full_name`, `is_active`; roles `admin` / `recruiter` / `manager` / `applicant` |
| `job_postings` | + structured criteria: required/preferred skills, `min_years_experience`, `min_zqf_level`, preferred fields of study, required/preferred certifications, per-job `scoring_weights`, `description_embedding vector` |
| `applications` | + `source` (portal/email/webhook/api), `external_ref` (idempotency), cover letter text/summary/embedding, `fit_score`, `score_breakdown`, `scoring_version`, `processing_error` |
| `qualifications` | one row per claimed academic award or certification: ZQF level, field, year, classification, `verification_status`, confidence, check-by-check details, link to institution + source document |
| `institutions` | shared registry (mock ZAQA / HEA / TEVETA snapshot) — not tenant-scoped |
| `audit_logs` | append-only (Postgres trigger blocks UPDATE/DELETE): submissions, parsing, scoring, recruiter views, job edits |

Migration: `packages/db-schema/migrations/versions/0002_ats_scoring.py` (pgvector, HNSW index, RLS on new tenant tables).

## Verification statuses

| Status | Meaning | Education trust |
|---|---|---|
| `verified` | Local HEA/TEVETA-registered institution, award within its ZQF ceiling, dates consistent | 1.0 |
| `recognised_foreign` | Recognised foreign university; ZAQA foreign-qualification evaluation advised | 0.9 |
| `needs_review` | Fuzzy institution match, provisional registration, level above institution's ceiling, or award year before founding / in future | 0.6 |
| `unverified` | Institution missing or not in registry | 0.4 |
| `unrecognised` | Institution deregistered / unaccredited | 0.0 |

"Verified" means **registry-consistent**, not "certificate proven authentic". Authenticity needs a live
ZAQA verification request; swap `InstitutionRegistry` / the seeded `institutions` table for a live source.

## Candidate Fit Score (0–100)

| Component | Weight | How |
|---|---|---|
| Skills & experience | 40% | 0.7 × weighted skill coverage (required ×2, preferred ×1) + 0.3 × min(1, years / required years); overlapping jobs counted once |
| Cover letter | 20% | 0.75 × semantic relevance to the job (embeddings if configured, else lexical cosine) + 0.25 × share of key skills mentioned; ×0.7 if under 80 words |
| Education / ZQF | 30% | best award of: level fit vs `min_zqf_level` (≥ → 1.0, −1 → 0.6, −2 → 0.3) × verification trust × field relevance (0.85 if outside preferred fields) |
| Certifications | 10% | weighted coverage of required/preferred certs (aliases resolved, e.g. "Chartered Certified Accountant" = ACCA); if none specified: 0.5 + 0.25 per recognised cert |

Weights are configurable per job (`scoring_weights`, must sum to 1). Unmet requirements raise **flags**
for the reviewer rather than auto-rejecting. Every component carries a plain-language explanation.

## Endpoints

| Method | Path | Auth | |
|---|---|---|---|
| POST | `/auth/login` | — | JWT |
| GET | `/jobs/public`, `/jobs/public/{slug}` | — | open jobs |
| POST | `/jobs` | recruiter | create job with structured criteria (`min_qualification`: level, label or award title) |
| PATCH | `/jobs/{id}` | recruiter | edit criteria / close |
| GET | `/jobs/{id}/candidates` | recruiter | **ranked list**; `min_score`, `status`, `verified_only`, `limit`, `offset` |
| POST | `/applications/submit` | — | **multipart**: `job_id`, `candidate_name`, `candidate_email`, `cv`, optional `cover_letter` file or `cover_letter_text`, `certificates[]`; returns 202 |
| GET | `/applications/{id}/status` | — | processing status only (no score) |
| GET | `/applications/{id}/assessment` | recruiter | deep dive: breakdown, qualifications + checks, profile, cover-letter summary (audited) |
| POST | `/applications/{id}/rescore` | recruiter | recompute after criteria/profile edits |

## Configuration

See `apps/api/.env.example`. LLM features use any OpenAI-compatible endpoint (OpenAI, Groq, Ollama's `/v1`).

## Known gaps / next phase

- Registry and certification catalogue are **mock data** (`services/verification/registry_data.py`).
- Integration layer (inbound email parser, signed webhooks, API keys for external HR systems) — the
  `source` / `external_ref` columns and source-agnostic pipeline are in place for it.
- Postgres RLS policies exist but the app connects as the table owner, which bypasses RLS; production
  needs a non-owner app role (or `FORCE ROW LEVEL SECURITY`) plus a tenant lookup for public submissions.
- Scanned-PDF OCR (rasterise + OCR), applicant accounts, recruiter shortlist/reject workflow, and wiring the
  Next.js dashboard to these endpoints.
