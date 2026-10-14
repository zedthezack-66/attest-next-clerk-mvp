import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from apps.api.models.database import get_db, utcnow
from apps.api.models.entities import Application, JobPosting, Qualification, User
from apps.api.schemas.dto import JobCreate, JobOut, JobUpdate, QualificationOut, RankedCandidate, RankedCandidateList
from apps.api.services.audit import audit
from apps.api.services.dependencies import current_user, require_recruiter
from apps.api.services.scoring import SCORING_VERSION, VERIFICATION_TRUST
from apps.api.services.verification import VerificationStatus, level_from_requirement

router = APIRouter(prefix="/jobs", tags=["jobs"])

TRUSTED_STATUSES = [VerificationStatus.VERIFIED.value, VerificationStatus.RECOGNISED_FOREIGN.value]


@router.get("/public", response_model=list[JobOut])
def public_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(JobPosting).where(JobPosting.status == "open")).all()


@router.get("/public/{slug}", response_model=JobOut)
def public_job(slug: str, db: Session = Depends(get_db)):
    job = db.scalar(select(JobPosting).where(JobPosting.slug == slug, JobPosting.status == "open"))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[JobOut])
def dashboard_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(JobPosting).where(JobPosting.tenant_id == user.tenant_id)).all()


def _slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:200]
    return f"{base}-{uuid4().hex[:6]}"


def _apply_criteria(job: JobPosting, data: dict) -> None:
    if "min_qualification" in data:
        raw = data.pop("min_qualification")
        level = level_from_requirement(raw)
        if raw not in (None, "") and level is None:
            raise HTTPException(status_code=422, detail=f"Unrecognised minimum qualification '{raw}'")
        job.min_zqf_level = level
    for key, value in data.items():
        setattr(job, key, value)


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    job = JobPosting(tenant_id=user.tenant_id, slug=_slugify(body.title), created_by=user.id)
    _apply_criteria(job, body.model_dump())
    db.add(job)
    db.flush()
    audit(db, "job.created", "job", job.id, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id, title=job.title)
    db.commit()
    db.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobOut)
def update_job(job_id: UUID, body: JobUpdate, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    job = db.scalar(select(JobPosting).where(JobPosting.id == job_id, JobPosting.tenant_id == user.tenant_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    changes = body.model_dump(exclude_unset=True)
    _apply_criteria(job, dict(changes))
    job.updated_at = utcnow()
    audit(db, "job.updated", "job", job.id, tenant_id=user.tenant_id, actor_type="user", actor_id=user.id,
          fields=sorted(changes))
    db.commit()
    db.refresh(job)
    return job


def _best_qualification(quals: list[Qualification]) -> Qualification | None:
    academic = [q for q in quals if q.kind == "academic"]
    if not academic:
        return None
    return max(academic, key=lambda q: (VERIFICATION_TRUST[VerificationStatus(q.verification_status)] > 0.5, q.zqf_level or 0,
                                        VERIFICATION_TRUST[VerificationStatus(q.verification_status)]))


@router.get("/{job_id}/candidates", response_model=RankedCandidateList)
def ranked_candidates(
    job_id: UUID,
    min_score: float | None = Query(default=None, ge=0, le=100),
    status: str | None = Query(default=None, description="e.g. scored, processing, shortlisted"),
    verified_only: bool = Query(default=False, description="Only candidates with a registry-verified or recognised foreign award"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = db.scalar(select(JobPosting).where(JobPosting.id == job_id, JobPosting.tenant_id == user.tenant_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    filters = [Application.tenant_id == user.tenant_id, Application.job_posting_id == job.id]
    if min_score is not None:
        filters.append(Application.fit_score >= min_score)
    if status:
        filters.append(Application.status == status)
    if verified_only:
        filters.append(exists().where(
            Qualification.application_id == Application.id,
            Qualification.kind == "academic",
            Qualification.verification_status.in_(TRUSTED_STATUSES),
        ))

    total = db.scalar(select(func.count()).select_from(Application).where(*filters))
    apps = db.scalars(
        select(Application).where(*filters)
        .order_by(Application.fit_score.desc().nulls_last(), Application.submitted_at.asc())
        .limit(limit).offset(offset)
    ).all()

    quals_by_app: dict[UUID, list[Qualification]] = {}
    if apps:
        for q in db.scalars(select(Qualification).where(Qualification.application_id.in_([a.id for a in apps]))):
            quals_by_app.setdefault(q.application_id, []).append(q)

    items = []
    for i, app in enumerate(apps):
        breakdown = app.score_breakdown or {}
        best = _best_qualification(quals_by_app.get(app.id, []))
        items.append(RankedCandidate(
            rank=offset + i + 1,
            application_id=app.id,
            candidate_name=app.candidate_name,
            candidate_email=app.candidate_email,
            status=app.status,
            source=app.source,
            submitted_at=app.submitted_at,
            fit_score=app.fit_score,
            components=breakdown.get("components", {}),
            flags=breakdown.get("flags", []),
            best_qualification=QualificationOut.model_validate(best) if best else None,
        ))
    return RankedCandidateList(job_id=job.id, job_title=job.title, total=total, limit=limit, offset=offset,
                               scoring_version=SCORING_VERSION, items=items)
