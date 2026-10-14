"""Development seed data: pilot tenant, recruiter login, demo job, and the mock institution registry."""

import os

from sqlalchemy import select, text

from apps.api.models.database import Base, SessionLocal, engine
from apps.api.models.entities import Institution, JobPosting, Tenant, User
from apps.api.services.auth import hash_password
from apps.api.services.verification.registry_data import MOCK_INSTITUTIONS


def create_schema() -> None:
    """Dev convenience only; production schema changes go through Alembic (packages/db-schema)."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("create extension if not exists vector"))
    Base.metadata.create_all(bind=engine)


def seed_institutions(db) -> None:
    existing = {i.code: i for i in db.scalars(select(Institution))}
    for rec in MOCK_INSTITUTIONS:
        row = existing.get(rec.code) or Institution(code=rec.code)
        row.name, row.aliases, row.country_code = rec.name, list(rec.aliases), rec.country_code
        row.kind, row.regulator, row.registration_status = rec.kind, rec.regulator, rec.registration_status
        row.max_zqf_level, row.founded_year, row.source = rec.max_zqf_level, rec.founded_year, "mock_registry"
        db.add(row)


def seed(db) -> None:
    tenant = db.scalar(select(Tenant).where(Tenant.name == "Pilot Employer"))
    if not tenant:
        tenant = Tenant(name="Pilot Employer")
        db.add(tenant)
        db.flush()
    if not db.scalar(select(User).where(User.email == "manager@attest.local")):
        db.add(User(tenant_id=tenant.id, email="manager@attest.local", full_name="Pilot Recruiter",
                    password_hash=hash_password(os.getenv("SEED_MANAGER_PASSWORD", "password123")), role="recruiter"))
    if not db.scalar(select(JobPosting).where(JobPosting.slug == "finance-officer-lusaka")):
        db.add(JobPosting(
            tenant_id=tenant.id,
            title="Finance Officer",
            slug="finance-officer-lusaka",
            description="Manage reconciliations, statutory reporting, and grant controls for a Lusaka-based operations team.",
            location="Lusaka",
            employment_type="full_time",
            requirements_json={"qualification_level": "Diploma", "skills": ["Excel", "financial reporting", "controls"], "documents": ["CV", "certificate"]},
            required_skills=["Excel", "financial reporting", "reconciliations"],
            preferred_skills=["IFRS", "Sage", "grant management", "budgeting"],
            min_years_experience=3,
            min_zqf_level=6,
            preferred_fields_of_study=["Accountancy", "Accounting", "Finance"],
            preferred_certifications=["ACCA", "CA Zambia"],
            status="open",
        ))
    seed_institutions(db)
    db.commit()


def init_dev_database() -> None:
    create_schema()
    with SessionLocal() as db:
        seed(db)
