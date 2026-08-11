from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models.database import get_db
from apps.api.models.entities import JobPosting, User
from apps.api.services.dependencies import current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/public")
def public_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(JobPosting).where(JobPosting.status == "open")).all()


@router.get("/public/{slug}")
def public_job(slug: str, db: Session = Depends(get_db)):
    return db.scalar(select(JobPosting).where(JobPosting.slug == slug, JobPosting.status == "open"))


@router.get("")
def dashboard_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(JobPosting).where(JobPosting.tenant_id == user.tenant_id)).all()

