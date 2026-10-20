from contextlib import asynccontextmanager
import json
from pathlib import Path
import tempfile
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .ingestion_config import IngestionSettings
from .repository import JobRepository, QueueFull, TERMINAL
from .services.youtube_service import IngestionError, canonicalize_youtube_url, download_audio
from .worker import LocalWorker
from .verification_config import VerificationSettings


class BoundedBodyMiddleware:
    """Bound even chunked multipart bodies before the multipart parser can spool them."""
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/v1/jobs":
            return await self.app(scope, receive, send)
        total = 0
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as body:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                part = message.get("body", b"")
                total += len(part)
                if total > self.max_bytes:
                    response = JSONResponse({"error": {"code": "source_too_large", "message": "Upload exceeds the configured request size limit."}}, status_code=413)
                    return await response(scope, receive, send)
                body.write(part)
                if not message.get("more_body", False):
                    break
            body.seek(0)
            remaining = total
            sent_end = False

            async def replay():
                nonlocal remaining, sent_end
                if remaining:
                    chunk = body.read(65536)
                    remaining -= len(chunk)
                    sent_end = remaining == 0
                    return {"type": "http.request", "body": chunk, "more_body": remaining > 0}
                if not sent_end:
                    sent_end = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                return await receive()

            await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, limits: IngestionSettings | None = None,
               transcriber=None, downloader=download_audio, start_worker=True,
               verification_settings=None, verifier=None, writing_settings=None, writer=None):
    settings = settings or Settings.from_env()
    limits = limits or IngestionSettings.from_env()
    storage = limits.storage_dir.resolve()
    repository = JobRepository(storage / "jobs.sqlite3")
    # Paths must stay stable even if a caller supplied a relative storage directory.
    from dataclasses import replace
    limits = replace(limits, storage_dir=storage)
    verification_settings = verification_settings or VerificationSettings.from_env()
    worker = LocalWorker(repository, settings, limits, transcriber, downloader, verification_settings, verifier,
                         writing_settings, writer)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        yield
        if start_worker:
            worker.close()

    app = FastAPI(title="VideoMind AI", version="0.4.0", lifespan=lifespan,
                  description="Local transcription and direct Ollama transcript rewriting into DOCX, with optional audio verification.")
    app.state.repository, app.state.worker = repository, worker
    app.add_middleware(BoundedBodyMiddleware, max_bytes=limits.max_bytes + 65536)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    @app.middleware("http")
    async def local_origin(request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in {"http://localhost:8000", "http://127.0.0.1:8000"}:
            return JSONResponse({"error": {"code": "invalid_origin", "message": "Cross-origin requests are not allowed."}}, status_code=403)
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": exc.detail}
        return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": {"code": "invalid_request", "message": "Check the required fields and their types.",
            "fields": [".".join(str(part) for part in error["loc"]) for error in exc.errors()]}}, status_code=422)

    def get_job(job_id: UUID):
        job = repository.get(str(job_id))
        if job is None:
            raise HTTPException(404, {"code": "not_found", "message": "Job not found."})
        return job

    def raw_ready(job):
        path = storage / "jobs" / job["id"] / "transcription" / "manifest.json"
        try:
            manifest = json.loads(path.read_text())
            return manifest.get("state") == "completed" and manifest.get("kind") == "raw_transcript"
        except (OSError, ValueError):
            return False

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "worker_running": bool(worker.thread and worker.thread.is_alive() and not worker.stop.is_set()),
                "max_upload_bytes": limits.max_bytes, "max_duration_seconds": limits.max_duration,
                "writing_pipeline": "direct", "audio_verification_default": False}

    def public_job(job):
        available = raw_ready(job)
        artifacts = ["raw_transcript.txt", "raw_transcript.json"] if available else []
        if (job["state"] == "completed" or (job["error"] or {}).get("code") == "document_failed") and job["payload"].get("verify"):
            artifacts.extend(["verified_transcript.txt", "verified_transcript.json", "verification.json"])
            directory = storage / "jobs" / job["id"] / "verification"
            artifacts.extend(name for name in ("document_source.txt", "document_source.json") if (directory / name).is_file())
        if job["state"] == "completed" and job["payload"].get("write_document"):
            directory = storage / "jobs" / job["id"] / "document"
            artifacts.extend(name for name in ("document.docx", "document.json", "knowledge.json", "quality.json",
                "reading_document.json", "content_gate.json", "rewrite_audit.json", "source_chunks.json") if (directory / name).is_file())
        return {
            key: job[key] for key in ("id", "state", "stage", "progress", "cancel_requested", "metadata", "error", "created_at", "updated_at")
        } | {"source_kind": job["payload"]["kind"], "audio_verified": False,
             "artifacts": artifacts, "verification": (job["metadata"] or {}).get("verification"),
             "document": (job["metadata"] or {}).get("document")}

    @app.post("/api/v1/jobs", status_code=202)
    async def create_job(
        authorized: Annotated[bool, Form()],
        youtube_url: Annotated[str | None, Form()] = None,
        file: Annotated[UploadFile | None, File()] = None,
        verify: Annotated[bool, Form()] = False,
        write_document: Annotated[bool, Form()] = False,
    ):
        if bool(youtube_url) == (file is not None):
            raise HTTPException(422, {"code": "invalid_source", "message": "Supply exactly one YouTube URL or audio file."})
        if not authorized:
            raise HTTPException(422, {"code": "authorization_required", "message": "Confirm that you are authorized to process this media."})
        if verify:
            # Cheap alias check here; full checkpoint hashes are checked in the worker.
            def name(model):
                return model.lower().removeprefix("systran/faster-whisper-")
            if name(settings.model) == name(verification_settings.model):
                raise HTTPException(422, {"code": "same_verification_model", "message": "Configure a different verification ASR checkpoint."})
        if start_worker and (worker.thread is None or not worker.thread.is_alive() or worker.stop.is_set()):
            raise HTTPException(503, {"code": "worker_unavailable", "message": "The local worker is unavailable."})
        try:
            canonical = canonicalize_youtube_url(youtube_url) if youtube_url else None
        except IngestionError as exc:
            raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc
        job_id = str(uuid4())
        folder = storage / "jobs" / job_id
        folder.mkdir(parents=True, exist_ok=False, mode=0o700)
        submitted = False
        try:
            if file is not None:
                count = 0
                with (folder / "source.audio").open("xb") as target:
                    while part := await file.read(65536):
                        count += len(part)
                        if count > limits.max_bytes:
                            raise HTTPException(413, {"code": "source_too_large", "message": "Audio exceeds the upload limit."})
                        target.write(part)
                if not count:
                    raise HTTPException(422, {"code": "empty_upload", "message": "The audio upload is empty."})
                payload = {"kind": "upload", "filename": Path((file.filename or "audio").replace("\\", "/")).name[:200], "authorized": True}
            else:
                payload = {"kind": "youtube", "url": canonical, "authorized": True}
            payload["verify"] = verify
            payload["write_document"] = write_document
            repository.add(job_id, payload, limits.max_jobs)
            submitted = True
        except QueueFull as exc:
            raise HTTPException(429, {"code": "queue_full", "message": str(exc)}) from exc
        finally:
            if file is not None:
                await file.close()
            if not submitted:
                (folder / "source.audio").unlink(missing_ok=True)
                folder.rmdir()
        worker.wake.set()
        return JSONResponse(public_job(repository.get(job_id)), status_code=202,
                            headers={"Location": f"/api/v1/jobs/{job_id}"})

    @app.get("/api/v1/jobs/{job_id}")
    def job_status(job_id: UUID):
        return public_job(get_job(job_id))

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: UUID):
        get_job(job_id)
        repository.cancel(str(job_id))
        job = get_job(job_id)
        return JSONResponse(public_job(job), status_code=200 if job["state"] in TERMINAL else 202)

    @app.get("/api/v1/jobs/{job_id}/transcript")
    def transcript(job_id: UUID, kind: str = "raw", format: str = "json", download: bool = False):
        job = get_job(job_id)
        if kind not in {"raw", "verified"} or format not in {"txt", "json"}:
            raise HTTPException(422, {"code": "unsupported_output", "message": "Choose raw or verified TXT/JSON."})
        if kind == "verified" and not job["payload"].get("verify"):
            raise HTTPException(422, {"code": "verification_not_requested", "message": "This job did not request audio verification."})
        raw_after_failed_review = job["state"] == "failed" and ((job["error"] or {}).get("code") == "document_failed" or
            kind == "raw" and (job["error"] or {}).get("code") == "verification_failed")
        if job["state"] != "completed" and not raw_after_failed_review and not (kind == "raw" and raw_ready(job)):
            raise HTTPException(409, {"code": "artifact_not_ready", "message": "The transcript is not available."})
        path = storage / "jobs" / str(job_id) / ("transcription" if kind == "raw" else "verification") / f"{kind}_transcript.{format}"
        if not path.is_file():
            raise HTTPException(404, {"code": "artifact_missing", "message": "The transcript artifact is missing."})
        if format == "json" and not download:
            return json.loads(path.read_text(encoding="utf-8"))
        return FileResponse(path, media_type="text/plain; charset=utf-8" if format == "txt" else "application/json",
                            filename=f"videomind-{job_id}-{kind}-transcript.{format}")

    @app.get("/api/v1/jobs/{job_id}/verification")
    def verification_report(job_id: UUID):
        job = get_job(job_id)
        if (job["state"] != "completed" and (job["error"] or {}).get("code") != "document_failed") or not job["payload"].get("verify"):
            raise HTTPException(409, {"code": "verification_not_ready", "message": "No completed verification report is available."})
        path = storage / "jobs" / str(job_id) / "verification" / "verification.json"
        if not path.is_file():
            raise HTTPException(404, {"code": "artifact_missing", "message": "The verification report is missing."})
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/v1/jobs/{job_id}/document")
    def document(job_id: UUID, format: str = "docx"):
        job = get_job(job_id)
        if format not in {"docx", "json", "txt", "quality", "knowledge", "evidence", "content-gate", "rewrite-audit", "source-chunks"}:
            raise HTTPException(422, {"code": "unsupported_output", "message": "Choose DOCX, JSON, TXT, quality, rewrite-audit, source-chunks, or an available legacy report."})
        if job["state"] != "completed" or not job["payload"].get("write_document"):
            raise HTTPException(409, {"code": "document_not_ready", "message": "Request write_document=true when submitting a new job."})
        special = {"content-gate": "content_gate.json", "rewrite-audit": "rewrite_audit.json", "source-chunks": "source_chunks.json"}
        name = special.get(format) or (f"{format}.json" if format in {"quality", "knowledge", "evidence"} else f"document.{format}")
        path = storage / "jobs" / str(job_id) / "document" / name
        if format == "json" and path.with_name("reading_document.json").is_file():
            path = path.with_name("reading_document.json")
        if not path.is_file():
            raise HTTPException(404, {"code": "artifact_missing", "message": "The document artifact is missing."})
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if format == "docx" else "text/plain; charset=utf-8",
                            filename=f"videomind-{job_id}-document.{format}")

    @app.get("/api/v1/jobs/{job_id}/document-source")
    def document_source(job_id: UUID, format: str = "json"):
        job = get_job(job_id)
        if format not in {"txt", "json"}:
            raise HTTPException(422, {"code": "unsupported_output", "message": "Choose TXT or JSON."})
        if (job["state"] != "completed" and (job["error"] or {}).get("code") != "document_failed") or not job["payload"].get("verify"):
            raise HTTPException(409, {"code": "source_not_ready", "message": "Document preparation requires a completed verification job."})
        path = storage / "jobs" / str(job_id) / "verification" / f"document_source.{format}"
        if not path.is_file():
            raise HTTPException(404, {"code": "artifact_missing", "message": "No document source was prepared for this job."})
        if format == "json":
            return json.loads(path.read_text(encoding="utf-8"))
        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=f"videomind-{job_id}-document-source.txt")

    return app
