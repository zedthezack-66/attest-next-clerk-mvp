from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    # Plain str: EmailStr rejects reserved domains like the seeded manager@attest.local.
    email: str = Field(min_length=3, max_length=320)
    password: str


class UploadRequest(BaseModel):
    application_id: str
    filename: str
    content_type: str
    doc_type: str
    content_hash: str


class ApplicationCreate(BaseModel):
    job_posting_id: str
    candidate_name: str
    candidate_email: EmailStr


class CompleteUpload(BaseModel):
    application_id: str
    doc_type: str
    s3_key: str
    content_hash: str


class ProfileUpdate(BaseModel):
    bio_json: dict
    education_json: list
    experience_json: list
    skills_json: list
    links_json: list



# --- Phase 1: jobs, submissions, ranking ---------------------------------------------------


class ScoringWeightsIn(BaseModel):
    skills_experience: float = 0.40
    cover_letter: float = 0.20
    education: float = 0.30
    certifications: float = 0.10

    @model_validator(mode="after")
    def _sums_to_one(self):
        if abs(self.skills_experience + self.cover_letter + self.education + self.certifications - 1) > 1e-6:
            raise ValueError("weights must sum to 1.0")
        return self


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    description: str = Field(min_length=20)
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    min_years_experience: float = Field(default=0, ge=0, le=50)
    # ZQF level 1-10, a label ("Diploma", "Bachelor") or a full award title
    min_qualification: str | int | None = None
    preferred_fields_of_study: list[str] = []
    required_certifications: list[str] = []
    preferred_certifications: list[str] = []
    scoring_weights: ScoringWeightsIn | None = None
    deadline: datetime | None = None
    status: str = Field(default="open", pattern="^(draft|open|closed)$")


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    min_years_experience: float | None = Field(default=None, ge=0, le=50)
    min_qualification: str | int | None = None
    preferred_fields_of_study: list[str] | None = None
    required_certifications: list[str] | None = None
    preferred_certifications: list[str] | None = None
    scoring_weights: ScoringWeightsIn | None = None
    deadline: datetime | None = None
    status: str | None = Field(default=None, pattern="^(draft|open|closed)$")


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    slug: str
    description: str
    department: str | None
    location: str | None
    employment_type: str | None
    required_skills: list[str]
    preferred_skills: list[str]
    min_years_experience: float
    min_zqf_level: int | None
    preferred_fields_of_study: list[str]
    required_certifications: list[str]
    preferred_certifications: list[str]
    scoring_weights: dict | None
    deadline: datetime | None
    status: str


class SubmissionAccepted(BaseModel):
    application_id: UUID
    status: str
    documents: int
    status_url: str


class ApplicationStatusOut(BaseModel):
    """Public status for the submitter; deliberately excludes the score."""
    application_id: UUID
    status: str


class QualificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    title: str
    institution_name_raw: str | None
    award_level_label: str | None
    zqf_level: int | None
    field_of_study: str | None
    award_year: int | None
    classification: str | None
    verification_status: str
    verification_confidence: float
    verification_details: dict


class ComponentOut(BaseModel):
    score: float
    weight: float
    points: float
    explanation: str


class RankedCandidate(BaseModel):
    rank: int
    application_id: UUID
    candidate_name: str
    candidate_email: str
    status: str
    source: str
    submitted_at: datetime
    fit_score: float | None
    components: dict[str, ComponentOut] = {}
    flags: list[str] = []
    best_qualification: QualificationOut | None = None


class RankedCandidateList(BaseModel):
    job_id: UUID
    job_title: str
    total: int
    limit: int
    offset: int
    scoring_version: str
    items: list[RankedCandidate]


class CandidateAssessment(BaseModel):
    application_id: UUID
    job_id: UUID
    candidate_name: str
    candidate_email: str
    candidate_phone: str | None
    source: str
    status: str
    submitted_at: datetime
    fit_score: float | None
    score_breakdown: dict | None
    cover_letter_summary: str | None
    profile: dict | None
    qualifications: list[QualificationOut]
    documents: list[dict]
