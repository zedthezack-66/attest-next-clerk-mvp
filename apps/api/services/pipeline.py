"""Application processing pipeline.

    documents -> text extraction -> CV parsing -> qualification verification
              -> profile + qualification rows -> fit score -> audit trail

`process_application` is idempotent: re-running it rebuilds the derived rows for an application.
It is triggered from the submit endpoint via BackgroundTasks and can also be drained by
`workers/pipeline_worker.py` (PipelineJob rows of kind "process_application") for durability.
"""

import logging
import re
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from apps.api.models.database import SessionLocal, utcnow
from apps.api.models.entities import (
    Application,
    CandidateProfile,
    Document,
    ExtractionResult,
    Institution,
    JobPosting,
    PipelineJob,
    Qualification,
)
from apps.api.services.audit import audit
from apps.api.services.llm import LLMClient
from apps.api.services.parsing import CVParser, ParsedCV, extract_text, summarize_cover_letter
from apps.api.services.parsing.heuristics import heuristic_parse
from apps.api.services.scoring import (
    SCORING_VERSION,
    CandidateEvidence,
    JobCriteria,
    QualificationEvidence,
    ScoringWeights,
    score_candidate,
)
from apps.api.services.similarity import Similarity, similarity_from_env
from apps.api.services.storage import read_object
from apps.api.services.verification import InstitutionRegistry, VerificationStatus, level_from_requirement, verify_qualification
from apps.api.services.verification.verifier import CertificationCatalog

log = logging.getLogger(__name__)
PROCESS_APPLICATION = "process_application"


def job_criteria(job: JobPosting) -> JobCriteria:
    legacy = job.requirements_json or {}
    return JobCriteria(
        title=job.title,
        description=job.description,
        required_skills=job.required_skills or legacy.get("skills", []),
        preferred_skills=job.preferred_skills or [],
        min_years_experience=job.min_years_experience or 0,
        min_zqf_level=job.min_zqf_level or level_from_requirement(legacy.get("qualification_level")),
        preferred_fields_of_study=job.preferred_fields_of_study or [],
        required_certifications=job.required_certifications or [],
        preferred_certifications=job.preferred_certifications or [],
    )


def job_weights(job: JobPosting) -> ScoringWeights:
    return ScoringWeights(**job.scoring_weights) if job.scoring_weights else ScoringWeights()


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _persist_qualifications(db: Session, app: Application, cv: ParsedCV, certificate_docs: list[tuple[Document, str]],
                            registry: InstitutionRegistry, cv_doc: Document | None) -> list[Qualification]:
    db.execute(delete(Qualification).where(Qualification.application_id == app.id))

    # Awards claimed in the CV, plus any read off uploaded certificate scans.
    claims: dict[str, dict] = {}
    for e in cv.education:
        claims[_norm_title(e.title)] = {"entry": e, "document_id": cv_doc.id if cv_doc else None, "certificate_uploaded": False}
    for doc, text in certificate_docs:
        for e in heuristic_parse(text).education:
            key = _norm_title(e.title)
            if key in claims:
                claims[key]["certificate_uploaded"] = True
                claims[key]["document_id"] = doc.id
                if not claims[key]["entry"].institution and e.institution:
                    claims[key]["entry"].institution = e.institution
            else:
                claims[key] = {"entry": e, "document_id": doc.id, "certificate_uploaded": True}

    rows = []
    inst_ids = dict(db.execute(select(Institution.code, Institution.id)).all()) if claims else {}
    for claim in claims.values():
        e = claim["entry"]
        result = verify_qualification(e.title, e.institution, e.award_year, registry)
        details = result.details() | {"certificate_uploaded": claim["certificate_uploaded"]}
        rows.append(Qualification(
            tenant_id=app.tenant_id, application_id=app.id, document_id=claim["document_id"],
            institution_id=inst_ids.get(result.institution.code) if result.institution else None,
            kind="academic", title=e.title[:300], institution_name_raw=(e.institution or None),
            award_level_label=result.zqf_label, zqf_level=result.zqf_level, field_of_study=result.field_of_study,
            award_year=e.award_year, classification=e.classification, gpa=e.gpa,
            verification_status=result.status.value, verification_confidence=result.confidence,
            verification_details=details, verified_at=utcnow(),
        ))

    catalog = CertificationCatalog()
    for cert in cv.certifications:
        rec = catalog.resolve(cert.name)
        rows.append(Qualification(
            tenant_id=app.tenant_id, application_id=app.id, document_id=cv_doc.id if cv_doc else None,
            kind="certification", title=(rec.name if rec else cert.name)[:300],
            institution_name_raw=cert.issuer or (rec.issuer if rec else None), award_year=cert.year,
            verification_status=VerificationStatus.UNVERIFIED.value, verification_confidence=0.5 if rec else 0.2,
            verification_details={"catalog_code": rec.code if rec else None,
                                  "notes": ["Membership not checked against the issuing body's register."]},
            verified_at=utcnow(),
        ))
    db.add_all(rows)
    return rows


def _upsert_profile(db: Session, app: Application, cv: ParsedCV) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.application_id == app.id))
    if not profile:
        profile = CandidateProfile(tenant_id=app.tenant_id, application_id=app.id)
        db.add(profile)
    elif profile.last_edited_by:
        # A recruiter corrected this profile; keep their edits rather than overwrite with re-parsed data.
        return profile
    profile.bio_json = {
        "candidate_name": app.candidate_name,
        "summary": cv.summary,
        "contact": cv.contact.model_dump(),
        "total_experience_years": cv.total_experience_years,
        "certifications": [c.model_dump() for c in cv.certifications],
        "extraction_method": cv.extraction_method,
    }
    profile.education_json = [e.model_dump() for e in cv.education]
    profile.experience_json = [e.model_dump() for e in cv.experience]
    profile.skills_json = cv.skills
    profile.links_json = cv.links
    return profile


def score_application(db: Session, app: Application, similarity: Similarity | None = None, actor_id=None) -> None:
    """(Re)score from persisted state, so recruiter profile corrections are reflected."""
    job = db.get(JobPosting, app.job_posting_id)
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.application_id == app.id))
    quals = db.scalars(select(Qualification).where(Qualification.application_id == app.id)).all()
    evidence = CandidateEvidence(
        skills=list(profile.skills_json or []) if profile else [],
        total_experience_years=float((profile.bio_json or {}).get("total_experience_years") or 0) if profile else 0.0,
        qualifications=[
            QualificationEvidence(q.title, q.zqf_level, VerificationStatus(q.verification_status), q.institution_name_raw, q.field_of_study)
            for q in quals if q.kind == "academic"
        ],
        certifications=[q.title for q in quals if q.kind == "certification"],
        cover_letter_text=app.cover_letter_text,
    )
    result = score_candidate(job_criteria(job), evidence, job_weights(job), similarity or similarity_from_env())
    app.fit_score = result.total
    app.score_breakdown = result.to_dict()
    app.scoring_version = SCORING_VERSION
    app.scored_at = utcnow()
    audit(db, "application.scored", "application", app.id, tenant_id=app.tenant_id,
          actor_type="user" if actor_id else "system", actor_id=actor_id,
          fit_score=result.total, version=SCORING_VERSION, flags=result.flags)


def process_application(db: Session, application_id: UUID, parser: CVParser | None = None,
                        similarity: Similarity | None = None) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise LookupError(f"Application {application_id} not found")
    job = db.get(JobPosting, app.job_posting_id)
    llm = LLMClient.from_env()
    parser = parser or CVParser(llm)
    app.status, app.processing_error = "processing", None
    db.commit()

    try:
        criteria = job_criteria(job)
        docs = db.scalars(select(Document).where(Document.application_id == app.id).order_by(Document.uploaded_at)).all()
        cv, cv_doc, certificate_docs = ParsedCV(), None, []
        for doc in docs:
            extracted = extract_text(doc.original_filename or doc.s3_key, read_object(doc.s3_key))
            structured: dict = {}
            if doc.doc_type == "cv" and cv_doc is None:
                cv = parser.parse(extracted.text, criteria.required_skills + criteria.preferred_skills)
                cv_doc, structured = doc, cv.model_dump()
            elif doc.doc_type == "cover_letter" and not app.cover_letter_text:
                app.cover_letter_text = extracted.text.strip() or None
            elif doc.doc_type == "certificate" and extracted.text.strip():
                certificate_docs.append((doc, extracted.text))
            db.add(ExtractionResult(
                tenant_id=app.tenant_id, document_id=doc.id, raw_text=extracted.text, structured_json=structured,
                field_confidences_json={"raw_text": extracted.confidence, **(cv.field_confidences if structured else {})},
                extraction_method=extracted.method if not structured else f"{extracted.method}+{cv.extraction_method}",
            ))
            if extracted.method in {"ocr_unavailable", "unsupported"}:
                audit(db, "document.text_unavailable", "document", doc.id, tenant_id=app.tenant_id, method=extracted.method)

        registry = InstitutionRegistry.from_db(db)
        quals = _persist_qualifications(db, app, cv, certificate_docs, registry, cv_doc)
        _upsert_profile(db, app, cv)
        app.cover_letter_summary = summarize_cover_letter(app.cover_letter_text, criteria.text, llm)
        if llm and llm.embedding_model and app.cover_letter_text:
            vectors = llm.embed([app.cover_letter_text[:8000], criteria.text[:8000]])
            if vectors:
                app.cover_letter_embedding, job.description_embedding = vectors[0], vectors[1]
        db.flush()
        audit(db, "application.parsed", "application", app.id, tenant_id=app.tenant_id,
              documents=len(docs), extraction_method=cv.extraction_method,
              qualifications={q.title: q.verification_status for q in quals})
        score_application(db, app, similarity)
        app.status = "scored"
        db.commit()
    except Exception as exc:
        db.rollback()
        log.exception("Processing failed for application %s", application_id)
        app = db.get(Application, application_id)
        app.status, app.processing_error = "failed", f"{type(exc).__name__}: {exc}"[:2000]
        audit(db, "application.processing_failed", "application", app.id, tenant_id=app.tenant_id, error=app.processing_error)
        db.commit()
        raise
    return app


def run_pipeline_job(job_id: UUID, max_attempts: int = 3) -> None:
    """Entry point for BackgroundTasks and the worker: one PipelineJob, own session."""
    with SessionLocal() as db:
        # Atomic claim so the BackgroundTask and a worker never process the same job twice.
        claimed = db.execute(
            update(PipelineJob)
            .where(PipelineJob.id == job_id, PipelineJob.status.in_(["queued", "retry"]))
            .values(status="running", attempts=PipelineJob.attempts + 1, updated_at=utcnow())
        ).rowcount
        db.commit()
        if not claimed:
            return
        job = db.get(PipelineJob, job_id)
        try:
            process_application(db, UUID(job.payload["application_id"]))
            job.status = "done"
        except Exception as exc:  # noqa: BLE001 - recorded on the job row for retry/inspection
            job.status = "failed" if job.attempts >= max_attempts else "retry"
            job.last_error = str(exc)[:2000]
        job.updated_at = utcnow()
        db.commit()


def pending_job_ids(limit: int = 10) -> list[UUID]:
    with SessionLocal() as db:
        return list(db.scalars(
            select(PipelineJob.id)
            .where(PipelineJob.kind == PROCESS_APPLICATION, PipelineJob.status.in_(["queued", "retry"]))
            .order_by(PipelineJob.created_at).limit(limit)
        ))
