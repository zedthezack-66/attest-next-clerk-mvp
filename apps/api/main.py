import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from apps.api.routers import applications, auth, jobs
from apps.api.services.seed import init_dev_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("AUTO_CREATE_SCHEMA", "true").lower() == "true":
        init_dev_database()
    yield


app = FastAPI(title="Attest API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(applications.router)


@app.get("/health")
def health():
    return {"ok": True}


DEMO_PAGE = Path(__file__).parent / "demo" / "index.html"


@app.get("/demo", include_in_schema=False)
def demo_page():
    """Single-page recruiter demo (uses the seeded demo login)."""
    return FileResponse(DEMO_PAGE)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/demo")
