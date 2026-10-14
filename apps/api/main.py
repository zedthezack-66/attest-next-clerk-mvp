import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
