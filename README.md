# Attest Phase 1

Verification-first hiring intake for Zambia. This MVP has been pivoted to a single full-stack Next.js app with Clerk for hiring-manager authentication. There is no Docker requirement and no separate FastAPI/API service for local development.

## Run Locally

1. Install dependencies:

```bash
npm install
```

2. Create Clerk keys at https://clerk.com, then copy env values:

```bash
cp .env.example apps/web/.env.local
```

Set these in `apps/web/.env.local`:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

3. Start the app:

```bash
npm run dev:web
```

4. Open:

- Portal: http://localhost:3000
- Dashboard: http://localhost:3000/dashboard

## Phase 1 Notes

- Public candidates can browse roles and submit applications with documents.
- Hiring managers sign in with Clerk and review applications in `/dashboard`.
- Local MVP data is stored in `apps/web/data/attest.local.json`.
- Uploaded files are stored in `apps/web/storage/uploads`.
- Extraction is a local preview adapter. It preserves the same raw-text -> structured-profile workflow without forcing a paid OCR/LLM provider decision yet.
- The older Docker/FastAPI scaffold remains in the repo as a reference, but `apps/web` is the recommended MVP path.

## ATS Phase 1 API

`apps/api` now contains the ATS backend: CV parsing, ZAQA/ZQF-aligned qualification verification (mock registry), multi-factor candidate scoring, and ranked-candidate endpoints. See [docs/ats-phase1.md](docs/ats-phase1.md).
# attestu-next-clerk-mvp
