# Attest Phase 1 API Contract

The current MVP uses Next.js route handlers inside `apps/web`. Base URL: `http://localhost:3000`.

## Public Portal

- `GET /api/jobs` returns open job postings.
- `GET /api/jobs/{slug}` returns one open job posting.
- `POST /api/applications/upload` creates an application, stores uploaded files locally, runs preview extraction, and creates a candidate profile.

## Dashboard

- Clerk protects `/dashboard`.
- `GET /api/applications/{application_id}/review` returns the application, editable profile, document metadata, and latest extraction result.
- `PATCH /api/applications/{application_id}/profile` requires Clerk auth and updates the editable candidate profile.

## Upload Deduplication

Duplicate detection is scoped to `(application_id, content_hash)`.

## Tenant Boundary

The local file-backed MVP seeds one tenant. The data model retains `tenantId` on tenant-owned records so it can move cleanly to Supabase/Neon Postgres with row-level security.
