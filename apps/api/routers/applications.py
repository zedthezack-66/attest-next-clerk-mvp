from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models.database import get_db
from apps.api.models.entities import Application, CandidateProfile, Document, ExtractionResult, JobPosting, PipelineJob, User
from apps.api.schemas.dto import ApplicationCreate, CompleteUpload, ProfileUpdate, UploadRequest
from apps.api.services.dependencies import current_user
from apps.api.services.storage import presigned_put

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

