from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None


class EducationEntry(BaseModel):
    title: str = Field(description="Award title as written, e.g. 'Bachelor of Accountancy'")
    institution: str | None = Field(default=None, description="Awarding institution as written")
    award_year: int | None = Field(default=None, description="Year awarded / completed")
    classification: str | None = Field(default=None, description="e.g. Distinction, Merit, Upper Second, 2:1")
    gpa: float | None = None
    raw: str | None = Field(default=None, description="Source line(s) the entry was read from")


class ExperienceEntry(BaseModel):
    title: str | None = None
    organisation: str | None = None
    start: str | None = Field(default=None, description="YYYY-MM or YYYY")
    end: str | None = Field(default=None, description="YYYY-MM, YYYY, or 'present'")
    months: int | None = None
    raw: str | None = None


class CertificationEntry(BaseModel):
    name: str
    issuer: str | None = None
    year: int | None = None


class ParsedCV(BaseModel):
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    total_experience_years: float = 0.0
    skills: list[str] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    # extractor name -> field confidences; filled by the parser, not the LLM
    field_confidences: dict[str, float] = Field(default_factory=dict)
    extraction_method: str = "heuristic"
