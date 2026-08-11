"""phase 1 schema with tenant RLS"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_phase1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('create extension if not exists "uuid-ossp"')
    op.create_table("tenants", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")), sa.Column("name", sa.String(200), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")))
    for ddl in [
        """create table users (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), email varchar(320) not null unique, password_hash varchar(255) not null, role varchar(40) not null default 'manager')""",
        """create table job_postings (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), title varchar(240) not null, slug varchar(260) not null unique, description text not null, requirements_json jsonb not null default '{}', deadline timestamp null, status varchar(40) not null default 'open')""",
        """create table applications (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), job_posting_id uuid not null references job_postings(id), candidate_name varchar(240) not null, candidate_email varchar(320) not null, submitted_at timestamp not null default now(), status varchar(40) not null default 'submitted')""",
        """create table documents (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), application_id uuid not null references applications(id), doc_type varchar(40) not null, s3_key varchar(512) not null, content_hash varchar(64) not null, uploaded_at timestamp not null default now(), constraint uq_document_application_hash unique(application_id, content_hash))""",
        """create table extraction_results (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), document_id uuid not null references documents(id), raw_text text not null, structured_json jsonb not null default '{}', field_confidences_json jsonb not null default '{}', extraction_method varchar(40) not null, created_at timestamp not null default now())""",
        """create table candidate_profiles (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), application_id uuid not null unique references applications(id), bio_json jsonb not null default '{}', education_json jsonb not null default '[]', experience_json jsonb not null default '[]', skills_json jsonb not null default '[]', links_json jsonb not null default '[]', last_edited_by uuid null, last_edited_at timestamp null)""",
        """create table jobs (id uuid primary key default uuid_generate_v4(), tenant_id uuid not null references tenants(id), kind varchar(80) not null, status varchar(40) not null default 'queued', payload jsonb not null default '{}', attempts int not null default 0, last_error text null, created_at timestamp not null default now(), updated_at timestamp not null default now())""",
    ]:
        op.execute(ddl)
    for table in ["users", "job_postings", "applications", "documents", "extraction_results", "candidate_profiles", "jobs"]:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"create policy tenant_isolation_{table} on {table} using (tenant_id::text = current_setting('app.tenant_id', true))")


def downgrade():
    for table in ["jobs", "candidate_profiles", "extraction_results", "documents", "applications", "job_postings", "users", "tenants"]:
        op.drop_table(table)

