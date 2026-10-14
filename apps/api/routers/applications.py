import hashlib
import re
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models.database import get_db, set_tenant
from apps.api.models.entities import Application, CandidateProfile, Document, ExtractionResult, JobPosting, PipelineJob, Qualification, User
from apps.api.schemas.dto import (
    ApplicationCreate,
    ApplicationStatusOut,
    CandidateAssessment,
    CompleteUpload,
    ProfileUpdate,
    QualificationOut,
    SubmissionAccepted,
    UploadRequest,
)
from apps.api.services.audit import audit
from apps.api.services.dependencies import current_user, require_recruiter
from apps.api.services.parsing import SUPPORTED_EXTENSIONS
from apps.api.services.pipeline import PROCESS_APPLICATION, run_pipeline_job, score_application
from apps.api.services.storage import presigned_put, put_object

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("")
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    job = db.get(JobPosting, body.job_posting_id)
    if not job or job.status != "open":
        raise HTTPException(status_code=404, detail="Job not found")
    app = Application(tenant_id=job.tenant_id, job_posting_id=job.id, candidate_name=body.candidate_name, candidate_email=body.candidate_email)
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.post("/uploads/presign")
def presign_upload(body: UploadRequest, db: Session = Depends(get_db)):
    app = db.get(Application, body.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    existing = db.scalar(select(Document).where(Document.application_id == app.id, Document.content_hash == body.content_hash))
    if existing:
        return {"duplicate": True, "document_id": existing.id, "upload_url": None}
    key = f"{app.tenant_id}/{app.id}/{uuid4()}-{body.filename}"
    return {"duplicate": False, "s3_key": key, "upload_url": presigned_put(key, body.content_type)}


@router.post("/uploads/complete")
def complete_upload(body: CompleteUpload, db: Session = Depends(get_db)):
    app = db.get(Application, body.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    existing = db.scalar(select(Document).where(Document.application_id == app.id, Document.content_hash == body.content_hash))
    if existing:
        return {"duplicate": True, "document_id": existing.id}
    doc = Document(tenant_id=app.tenant_id, application_id=app.id, doc_type=body.doc_type, s3_key=body.s3_key, content_hash=body.content_hash)
    db.add(doc)
    db.flush()
    db.add(PipelineJob(tenant_id=app.tenant_id, kind="ocr", payload={"document_id": str(doc.id)}))
    db.commit()
    return {"duplicate": False, "document_id": doc.id}


@router.get("/jobs/{job_id}")
def list_for_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Application).where(Application.tenant_id == user.tenant_id, Application.job_posting_id == job_id)).all()


@router.get("/{application_id}/review")
def review(application_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = db.scalar(select(Application).where(Application.id == application_id, Application.tenant_id == user.tenant_id))
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.application_id == app.id))
    docs = db.scalars(select(Document).where(Document.application_id == app.id)).all()
    results = []
    for doc in docs:
        latest = db.scalars(select(ExtractionResult).where(ExtractionResult.document_id == doc.id).order_by(ExtractionResult.created_at.desc())).first()
        results.append({"document": doc, "latest_extraction": latest})
    return {"application": app, "profile": profile, "documents": results}


@router.patch("/{application_id}/profile")
def update_profile(application_id: str, body: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.application_id == application_id, CandidateProfile.tenant_id == user.tenant_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    for key, value in body.model_dump().items():
        setattr(profile, key, value)
    profile.last_edited_by = user.id
    from datetime import datetime
    profile.last_edited_at = datetime.utcnow()
    db.commit()
    return profile


# --- Phase 1: direct submission, assessment, re-scoring ------------------------------------

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CERTIFICATES = 10


async def _read_upload(upload: UploadFile) -> tuple[bytes, str]:
    name = Path(upload.filename or "upload").name
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {name}")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{name} exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    if not data:
        raise HTTPException(status_code=422, detail=f"{name} is empty")
    return data, name


@router.post("/submit", response_model=SubmissionAccepted, status_code=202)
async def submit_application(
    background: BackgroundTasks,
    job_id: Annotated[UUID, Form()],
    candidate_name: Annotated[str, Form(min_length=2, max_length=240)],
    candidate_email: Annotated[EmailStr, Form()],
    cv: Annotated[UploadFile, File(description="CV / resume (PDF, DOCX, TXT or image)")],
    candidate_phone: Annotated[str | None, Form(max_length=40)] = None,
    cover_letter_text: Annotated[str | None, Form(max_length=20000)] = None,
    cover_letter: Annotated[UploadFile | None, File()] = None,
    # Not Optional[...]: FastAPI 0.112 fails to coerce a single upload into Optional[list[UploadFile]].
    certificates: Annotated[list[UploadFile], File(description="Degree / professional certificates")] = [],  # noqa: B006
    db: Session = Depends(get_db),
):
    """Public portal submission. Files are stored, then parsing + verification + scoring runs in the background."""
    job = db.get(JobPosting, job_id)
    if not job or job.status != "open":
        raise HTTPException(status_code=404, detail="Job not found or closed")
    if len(certificates) > MAX_CERTIFICATES:
        raise HTTPException(status_code=422, detail=f"At most {MAX_CERTIFICATES} certificates")
    set_tenant(db, str(job.tenant_id))

    uploads = [("cv", await _read_upload(cv))]
    if cover_letter is not None and cover_letter.filename:
        uploads.append(("cover_letter", await _read_upload(cover_letter)))
    uploads += [("certificate", await _read_upload(c)) for c in certificates if c.filename]

    app = Application(
        tenant_id=job.tenant_id, job_posting_id=job.id, candidate_name=candidate_name.strip(),
        candidate_email=str(candidate_email).lower(), candidate_phone=candidate_phone,
        cover_letter_text=(cover_letter_text or "").strip() or None, source="portal",
    )
    db.add(app)
    db.flush()

    seen_hashes = set()
    for doc_type, (data, name) in uploads:
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[-120:]
        key = f"{job.tenant_id}/{app.id}/{uuid4()}-{safe}"
        put_object(key, data, "application/octet-stream")
        db.add(Document(tenant_id=job.tenant_id, application_id=app.id, doc_type=doc_type, s3_key=key,
                        content_hash=digest, original_filename=name, size_bytes=len(data)))

    pipeline_job = PipelineJob(tenant_id=job.tenant_id, kind=PROCESS_APPLICATION, payload={"application_id": str(app.id)})
    db.add(pipeline_job)
    audit(db, "application.submitted", "application", app.id, tenant_id=job.tenant_id, actor_type="public",
          job_id=str(job.id), source="portal", documents=len(seen_hashes))
    db.commit()

    background.add_task(run_pipeline_job, pipeline_job.id)
    return SubmissionAccepted(application_id=app.id, status=app.status, documents=len(seen_hashes),
                              status_url=f"/applications/{app.id}/status")


@router.get("/{application_id}/status", response_model=ApplicationStatusOut)
def application_status(application_id: UUID, db: Session = Depends(get_db)):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationStatusOut(application_id=app.id, status=app.status)


def _tenant_application(db: Session, application_id: UUID, user: User) -> Application:
    app = db.scalar(select(Application).where(Application.id == application_id, Application.tenant_id == user.tenant_id))
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _assessment(db: Session, app: Application) -> CandidateAssessment:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.application_id == app.id))
    quals = db.scalars(select(Qualification).where(Qualification.application_id == app.id)).all()
    docs = db.scalars(select(Document).where(Document.application_id == app.id)).all()
    return CandidateAssessment(
        application_id=app.id, job_id=app.job_posting_id, candidate_name=app.candidate_name,
        candidate_email=app.candidate_email, candidate_phone=app.candidate_phone, source=app.source,
        status=app.status, submitted_at=app.submitted_at, fit_score=app.fit_score,
        score_breakdown=app.score_breakdown, cover_letter_summary=app.cover_letter_summary,
        profile={
            "bio": profile.bio_json, "education": profile.education_json, "experience": profile.experience_json,
            "skills": profile.skills_json, "links": profile.links_json,
        } if profile else None,
        qualifications=[QualificationOut.model_validate(q) for q in quals],
        documents=[{"id": str(d.id), "doc_type": d.doc_type, "filename": d.original_filename,
                    "size_bytes": d.size_bytes, "uploaded_at": d.uploaded_at.isoformat()} for d in docs],
    )


@router.get("/{application_id}/assessment", response_model=CandidateAssessment)
def candidate_assessment(application_id: UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """Recruiter deep-dive: score breakdown, verified qualifications, parsed profile, cover letter summary."""
    app = _tenant_application(db, application_id, user)
    audit(db, "application.viewed", "application", app.id, tenant_id=app.tenant_id, actor_type="user", actor_id=user.id)
    db.commit()
    return _assessment(db, app)


@router.post("/{application_id}/rescore", response_model=CandidateAssessment)
def rescore(application_id: UUID, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """Recompute the fit score from stored data, e.g. after job criteria or the profile were edited."""
    app = _tenant_application(db, application_id, user)
    if app.status in {"submitted", "processing"}:
        raise HTTPException(status_code=409, detail="Application is still being processed")
    score_application(db, app, actor_id=user.id)
    db.commit()
    return _assessment(db, app)

