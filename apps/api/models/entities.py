import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, JSONType, utcnow, vector_type


def uuid_pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # admin | recruiter | manager | applicant
    role: Mapped[str] = mapped_column(String(40), default="manager")
    full_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class JobPosting(Base):
    __tablename__ = "job_postings"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    slug: Mapped[str] = mapped_column(String(260), unique=True)
    description: Mapped[str] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Legacy free-form requirements; structured criteria below take precedence when set.
    requirements_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    required_skills: Mapped[list] = mapped_column(JSONType, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSONType, default=list)
    min_years_experience: Mapped[float] = mapped_column(Float, default=0)
    min_zqf_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_fields_of_study: Mapped[list] = mapped_column(JSONType, default=list)
    required_certifications: Mapped[list] = mapped_column(JSONType, default=list)
    preferred_certifications: Mapped[list] = mapped_column(JSONType, default=list)
    scoring_weights: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    description_embedding = mapped_column(vector_type(), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # draft | open | closed
    status: Mapped[str] = mapped_column(String(40), default="open")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_job_score", "job_posting_id", "fit_score"),
        UniqueConstraint("tenant_id", "source", "external_ref", name="uq_application_external_ref"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    job_posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id"), index=True)
    applicant_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    candidate_name: Mapped[str] = mapped_column(String(240))
    candidate_email: Mapped[str] = mapped_column(String(320))
    candidate_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # portal | email | webhook | api
    source: Mapped[str] = mapped_column(String(40), default="portal")
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # submitted | processing | scored | failed  (recruiter decisions: shortlisted | rejected | interview)
    status: Mapped[str] = mapped_column(String(40), default="submitted")
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_embedding = mapped_column(vector_type(), nullable=True)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    scoring_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job = relationship("JobPosting", back_populates="applications")
    qualifications = relationship("Qualification", back_populates="application", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("application_id", "content_hash", name="uq_document_application_hash"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    # cv | cover_letter | certificate | national_id
    doc_type: Mapped[str] = mapped_column(String(40))
    s3_key: Mapped[str] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    original_filename: Mapped[str | None] = mapped_column(String(260), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExtractionResult(Base):
    __tablename__ = "extraction_results"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    field_confidences_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    extraction_method: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), unique=True, index=True)
    bio_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    education_json: Mapped[list] = mapped_column(JSONType, default=list)
    experience_json: Mapped[list] = mapped_column(JSONType, default=list)
    skills_json: Mapped[list] = mapped_column(JSONType, default=list)
    links_json: Mapped[list] = mapped_column(JSONType, default=list)
    last_edited_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Institution(Base):
    """Shared reference registry (not tenant-scoped). Seeded from a mock ZAQA/HEA/TEVETA snapshot."""

    __tablename__ = "institutions"
    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(240))
    aliases: Mapped[list] = mapped_column(JSONType, default=list)
    country_code: Mapped[str] = mapped_column(String(2))
    # public_university | private_university | college | foreign_university
    kind: Mapped[str] = mapped_column(String(40))
    # HEA | TEVETA | FOREIGN
    regulator: Mapped[str] = mapped_column(String(40))
    # registered | provisional | recognised | deregistered | unaccredited
    registration_status: Mapped[str] = mapped_column(String(40))
    max_zqf_level: Mapped[int] = mapped_column(Integer)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(60), default="mock_registry")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Qualification(Base):
    """An academic award or professional certification claimed by a candidate, with its verification outcome."""

    __tablename__ = "qualifications"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    # academic | certification
    kind: Mapped[str] = mapped_column(String(20), default="academic")
    title: Mapped[str] = mapped_column(String(300))
    institution_name_raw: Mapped[str | None] = mapped_column(String(300), nullable=True)
    award_level_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    zqf_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(200), nullable=True)
    award_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    # verified | recognised_foreign | needs_review | unverified | unrecognised
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    verification_confidence: Mapped[float] = mapped_column(Float, default=0)
    verification_details: Mapped[dict] = mapped_column(JSONType, default=dict)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    application = relationship("Application", back_populates="qualifications")


class AuditLog(Base):
    """Append-only trail of who did what to which record (Postgres trigger blocks UPDATE/DELETE)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    # user | system | integration | public
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PipelineJob(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
