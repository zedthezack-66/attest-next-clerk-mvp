"""ATS phase 1: job criteria, scoring, qualifications/verification, institution registry, audit logs, pgvector"""

import os

from alembic import op

revision = "0002_ats_scoring"
down_revision = "0001_phase1"
branch_labels = None
depends_on = None

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))


def upgrade():
    op.execute("create extension if not exists vector")

    op.execute("""
        alter table users
            add column full_name varchar(240) null,
            add column is_active boolean not null default true,
            add column created_at timestamp not null default now()
    """)

    op.execute(f"""
        alter table job_postings
            add column department varchar(160) null,
            add column location varchar(160) null,
            add column employment_type varchar(40) null,
            add column required_skills jsonb not null default '[]',
            add column preferred_skills jsonb not null default '[]',
            add column min_years_experience double precision not null default 0,
            add column min_zqf_level int null check (min_zqf_level between 1 and 10),
            add column preferred_fields_of_study jsonb not null default '[]',
            add column required_certifications jsonb not null default '[]',
            add column preferred_certifications jsonb not null default '[]',
            add column scoring_weights jsonb null,
            add column description_embedding vector({EMBEDDING_DIM}) null,
            add column created_by uuid null references users(id),
            add column created_at timestamp not null default now(),
            add column updated_at timestamp not null default now()
    """)

    op.execute(f"""
        alter table applications
            add column applicant_user_id uuid null references users(id),
            add column candidate_phone varchar(40) null,
            add column source varchar(40) not null default 'portal',
            add column external_ref varchar(255) null,
            add column cover_letter_text text null,
            add column cover_letter_summary text null,
            add column cover_letter_embedding vector({EMBEDDING_DIM}) null,
            add column fit_score double precision null check (fit_score between 0 and 100),
            add column score_breakdown jsonb null,
            add column scoring_version varchar(40) null,
            add column scored_at timestamp null,
            add column processing_error text null,
            add constraint uq_application_external_ref unique (tenant_id, source, external_ref)
    """)
    op.execute("create index ix_applications_job_score on applications (job_posting_id, fit_score desc nulls last)")
    op.execute("create index ix_applications_cover_letter_embedding on applications using hnsw (cover_letter_embedding vector_cosine_ops)")

    op.execute("""
        alter table documents
            add column original_filename varchar(260) null,
            add column content_type varchar(120) null,
            add column size_bytes int null
    """)

    # Shared reference data: not tenant-scoped, so no RLS.
    op.execute("""
        create table institutions (
            id uuid primary key default uuid_generate_v4(),
            code varchar(60) not null unique,
            name varchar(240) not null,
            aliases jsonb not null default '[]',
            country_code varchar(2) not null,
            kind varchar(40) not null,
            regulator varchar(40) not null,
            registration_status varchar(40) not null,
            max_zqf_level int not null check (max_zqf_level between 1 and 10),
            founded_year int null,
            source varchar(60) not null default 'mock_registry',
            updated_at timestamp not null default now()
        )
    """)

    op.execute("""
        create table qualifications (
            id uuid primary key default uuid_generate_v4(),
            tenant_id uuid not null references tenants(id),
            application_id uuid not null references applications(id) on delete cascade,
            document_id uuid null references documents(id),
            institution_id uuid null references institutions(id),
            kind varchar(20) not null default 'academic' check (kind in ('academic', 'certification')),
            title varchar(300) not null,
            institution_name_raw varchar(300) null,
            award_level_label varchar(60) null,
            zqf_level int null check (zqf_level between 1 and 10),
            field_of_study varchar(200) null,
            award_year int null,
            classification varchar(60) null,
            gpa double precision null,
            verification_status varchar(32) not null default 'unverified'
                check (verification_status in ('verified', 'recognised_foreign', 'needs_review', 'unverified', 'unrecognised')),
            verification_confidence double precision not null default 0,
            verification_details jsonb not null default '{}',
            verified_at timestamp null,
            created_at timestamp not null default now()
        )
    """)
    op.execute("create index ix_qualifications_application on qualifications (application_id)")
    op.execute("create index ix_qualifications_status on qualifications (verification_status)")

    op.execute("""
        create table audit_logs (
            id uuid primary key default uuid_generate_v4(),
            tenant_id uuid null references tenants(id),
            actor_type varchar(20) not null,
            actor_id varchar(80) null,
            action varchar(80) not null,
            entity_type varchar(60) not null,
            entity_id varchar(80) not null,
            details jsonb not null default '{}',
            created_at timestamp not null default now()
        )
    """)
    op.execute("create index ix_audit_entity on audit_logs (entity_type, entity_id)")
    op.execute("create index ix_audit_tenant_created on audit_logs (tenant_id, created_at desc)")
    # Append-only: block UPDATE/DELETE on the audit trail.
    op.execute("""
        create or replace function audit_logs_immutable() returns trigger language plpgsql as $$
        begin
            raise exception 'audit_logs is append-only';
        end $$
    """)
    op.execute("""
        create trigger trg_audit_logs_immutable before update or delete on audit_logs
        for each row execute function audit_logs_immutable()
    """)

    op.execute("alter table qualifications enable row level security")
    op.execute("create policy tenant_isolation_qualifications on qualifications using (tenant_id::text = current_setting('app.tenant_id', true))")
    op.execute("alter table audit_logs enable row level security")
    op.execute("create policy tenant_isolation_audit_logs on audit_logs using (tenant_id::text = current_setting('app.tenant_id', true))")


def downgrade():
    op.execute("drop trigger if exists trg_audit_logs_immutable on audit_logs")
    op.execute("drop function if exists audit_logs_immutable()")
    op.drop_table("audit_logs")
    op.drop_table("qualifications")
    op.drop_table("institutions")
    op.execute("alter table documents drop column original_filename, drop column content_type, drop column size_bytes")
    op.execute("drop index if exists ix_applications_cover_letter_embedding")
    op.execute("drop index if exists ix_applications_job_score")
    op.execute("""
        alter table applications
            drop constraint uq_application_external_ref,
            drop column applicant_user_id, drop column candidate_phone, drop column source, drop column external_ref,
            drop column cover_letter_text, drop column cover_letter_summary, drop column cover_letter_embedding,
            drop column fit_score, drop column score_breakdown, drop column scoring_version, drop column scored_at,
            drop column processing_error
    """)
    op.execute("""
        alter table job_postings
            drop column department, drop column location, drop column employment_type, drop column required_skills,
            drop column preferred_skills, drop column min_years_experience, drop column min_zqf_level,
            drop column preferred_fields_of_study, drop column required_certifications, drop column preferred_certifications,
            drop column scoring_weights, drop column description_embedding, drop column created_by,
            drop column created_at, drop column updated_at
    """)
    op.execute("alter table users drop column full_name, drop column is_active, drop column created_at")
