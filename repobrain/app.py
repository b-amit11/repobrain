from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .answers import answer, configured
from .store import default_store


class IndexRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class Question(BaseModel):
    repo_id: int = Field(gt=0)
    question: str = Field(min_length=2, max_length=2000)


def create_app(store=None):
    store = store or default_store()
    jobs, lock = {}, threading.Lock()
    pool = ThreadPoolExecutor(max_workers=1)

    @asynccontextmanager
    async def lifespan(app):
        yield
        pool.shutdown(wait=True)

    app = FastAPI(title="RepoBrain", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        origin = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.get("/api/status")
    def status():
        return {"ai_configured": configured(), "version": "0.1.0", "language": "Python", "retrieval": "BM25"}

    @app.get("/api/repos")
    def repos():
        return store.repositories()

    def index_job(job_id, path):
        with lock:
            jobs[job_id] = {"status": "running"}
        try:
            result = {"status": "completed", "result": store.index(path)}
        except (ValueError, OSError) as exc:
            result = {"status": "failed", "error": str(exc)}
        except Exception:
            result = {"status": "failed", "error": "Indexing failed. The previous snapshot is still available."}
        with lock:
            jobs[job_id] = result

    @app.post("/api/index", status_code=202)
    def index(body: IndexRequest):
        with lock:
            if any(j["status"] in {"queued", "running"} for j in jobs.values()):
                raise HTTPException(409, "An index job is already running.")
            while len(jobs) >= 100:
                jobs.pop(next(iter(jobs)))
            job_id = uuid.uuid4().hex
            jobs[job_id] = {"status": "queued"}
        pool.submit(index_job, job_id, body.path)
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "Job not found. Jobs do not survive a server restart.")
            return jobs[job_id].copy()

    @app.post("/api/ask")
    def ask(body: Question):
        try:
            return answer(store, body.repo_id, body.question)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/source/{chunk_id}")
    def source(chunk_id: int):
        try:
            return store.source(chunk_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")

    return app
