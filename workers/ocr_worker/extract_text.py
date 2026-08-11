import io
import time
from datetime import datetime
from pathlib import Path
from sqlalchemy import select

from apps.api.models.database import SessionLocal
from apps.api.models.entities import Document, PipelineJob
from apps.api.services.storage import read_object
from workers.ocr_worker.confidence import confidence_for


def extract_text_from_bytes(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text, "direct_text"
        return "Scanned PDF detected. Configure a vision/OCR provider adapter for production extraction.", "ocr"
    if suffix == ".docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs), "direct_text"
    return "Image document uploaded. Local Phase 1 adapter recorded this for OCR provider processing.", "vision_llm"


def run_once() -> bool:
    with SessionLocal() as db:
        job = db.scalars(select(PipelineJob).where(PipelineJob.kind == "ocr", PipelineJob.status == "queued").order_by(PipelineJob.created_at).limit(1)).first()
        if not job:
            return False
        job.status = "running"
        job.attempts += 1
        db.commit()
        try:
            doc = db.get(Document, job.payload["document_id"])
            data = read_object(doc.s3_key)
            raw_text, method = extract_text_from_bytes(doc.s3_key, data)
            job.status = "done"
            job.updated_at = datetime.utcnow()
            db.add(PipelineJob(tenant_id=doc.tenant_id, kind="extract_structured", payload={"document_id": str(doc.id), "raw_text": raw_text, "method": method, "confidence": confidence_for(raw_text, method)}))
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

