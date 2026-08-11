import re
import time
from datetime import datetime
from sqlalchemy import select

from apps.api.models.database import SessionLocal
from apps.api.models.entities import Application, CandidateProfile, Document, ExtractionResult, PipelineJob


def local_structured_extraction(raw_text: str) -> tuple[dict, dict]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    email = next((m.group(0) for m in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)), None)
    skills = [s for s in ["Excel", "Python", "SQL", "financial reporting", "project management", "JavaScript"] if s.lower() in raw_text.lower()]
    education = []
    for line in lines:
        if any(word in line.lower() for word in ["diploma", "bachelor", "master", "degree", "certificate"]):
            education.append({"raw": line, "institution": None, "qualification": line, "year": None})
    structured = {
        "bio": {"summary": lines[0] if lines else "Awaiting extraction review"},
        "contact": {"email": email},
        "education": education,
        "experience": [{"raw": line} for line in lines if "experience" in line.lower()][:5],
        "skills": skills,
        "professional_bodies": [line for line in lines if any(body in line.upper() for body in ["EIZ", "ZICA", "LAZ", "HPCZ", "TCZ"])],
        "links": re.findall(r"https?://\S+", raw_text),
    }
    confidences = {
        "bio.summary": 0.66 if lines else 0.2,
        "contact.email": 0.95 if email else 0.1,
        "education": 0.7 if education else 0.25,
        "skills": 0.8 if skills else 0.3,
    }
    return structured, confidences


def upsert_profile(db, doc: Document, structured: dict):
    app = db.get(Application, doc.application_id)
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.application_id == app.id))
    if not profile:
        profile = CandidateProfile(tenant_id=doc.tenant_id, application_id=app.id)
        db.add(profile)
    profile.bio_json = {"candidate_name": app.candidate_name, **structured.get("bio", {}), "contact": structured.get("contact", {})}
    profile.education_json = structured.get("education", [])
    profile.experience_json = structured.get("experience", [])
    profile.skills_json = structured.get("skills", [])
    profile.links_json = structured.get("links", [])


def run_once() -> bool:
    with SessionLocal() as db:
        job = db.scalars(select(PipelineJob).where(PipelineJob.kind == "extract_structured", PipelineJob.status == "queued").order_by(PipelineJob.created_at).limit(1)).first()
        if not job:
            return False
        job.status = "running"
        job.attempts += 1
        db.commit()
        try:
            doc = db.get(Document, job.payload["document_id"])
            structured, field_conf = local_structured_extraction(job.payload["raw_text"])
            field_conf.update(job.payload.get("confidence", {}))
            db.add(ExtractionResult(tenant_id=doc.tenant_id, document_id=doc.id, raw_text=job.payload["raw_text"], structured_json=structured, field_confidences_json=field_conf, extraction_method=job.payload["method"]))
            upsert_profile(db, doc, structured)
            job.status = "done"
            job.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            job.status = "failed" if job.attempts >= 3 else "queued"
            job.last_error = str(exc)
            job.updated_at = datetime.utcnow()
            db.commit()
        return True


if __name__ == "__main__":
    while True:
        if not run_once():
            time.sleep(3)

