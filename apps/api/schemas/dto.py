from datetime import datetime
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
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

