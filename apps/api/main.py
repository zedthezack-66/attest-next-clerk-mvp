from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from apps.api.models.database import Base, SessionLocal, engine
from apps.api.models.entities import JobPosting, Tenant, User
from apps.api.routers import applications, auth, jobs
from apps.api.services.auth import hash_password

app = FastAPI(title="Attest API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(applications.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.name == "Pilot Employer"))
        if not tenant:
            tenant = Tenant(name="Pilot Employer")
            db.add(tenant)
            db.flush()
        if not db.scalar(select(User).where(User.email == "manager@attest.local")):
            db.add(User(tenant_id=tenant.id, email="manager@attest.local", password_hash=hash_password("password123"), role="manager"))
        if not db.scalar(select(JobPosting).where(JobPosting.slug == "finance-officer-lusaka")):
            db.add(JobPosting(
                tenant_id=tenant.id,
                title="Finance Officer",
                slug="finance-officer-lusaka",
                description="Manage reconciliations, statutory reporting, and grant controls for a Lusaka-based operations team.",
                requirements_json={"qualification_level": "Diploma", "skills": ["Excel", "financial reporting", "controls"], "documents": ["CV", "certificate"]},
                status="open",
            ))
        db.commit()


@app.get("/health")
def health():
    return {"ok": True}

