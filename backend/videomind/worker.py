"""Single local worker; API requests enqueue rather than performing inference."""
import fcntl
from pathlib import Path
import threading

from .config import Settings
from .ingestion_config import IngestionSettings
from .pipeline import run_pipeline
from .repository import JobRepository
from .services.audio_service import AudioError, duration
from .services.transcription_service import FasterWhisperTranscriber
from .services.youtube_service import IngestionError, download_audio
from .services.verification_service import verify_run
from .verification_config import VerificationSettings
from .writing_config import WritingSettings
from .services.writing_pipeline import generate_document


class JobCancelled(RuntimeError):
    pass


class LocalWorker:
    def __init__(self, repository: JobRepository, settings: Settings, limits: IngestionSettings,
                 transcriber=None, downloader=download_audio, verification_settings=None, verifier=None,
                 writing_settings=None, writer=None):
        self.repository, self.settings, self.limits = repository, settings, limits
        self.transcriber = transcriber if transcriber is not None else FasterWhisperTranscriber(settings)
        self.downloader = downloader
        self.verification_settings = verification_settings or VerificationSettings.from_env()
        self.verifier = verifier
        self.writing_settings = writing_settings or WritingSettings.from_env()
        self.writer = writer
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        self.lock = None

    def start(self):
        self.lock = (self.limits.storage_dir / "worker.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError("Another worker owns this storage directory. Run one API process.")
        self.repository.recover()
        self.thread = threading.Thread(target=self._run, name="videomind-worker", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=5)

    def _run(self):
        try:
            while not self.stop.is_set():
                self.wake.clear()
                if not self.run_one():
                    self.wake.wait(timeout=0.5)
        finally:
            self.lock.close()

    def run_one(self):
        job = self.repository.claim()
        if job is None:
            return False
        job_id = job["id"]
        folder = self.limits.storage_dir / "jobs" / job_id

        def check_cancel():
            if self.stop.is_set() or self.repository.get(job_id)["cancel_requested"]:
                raise JobCancelled("Job cancelled")

        try:
            check_cancel()
            if job["payload"]["kind"] == "youtube":
                source, metadata = self.downloader(
                    job["payload"]["url"], folder / "download", self.limits,
                    authorized=job["payload"]["authorized"], check_cancel=check_cancel,
                )
            else:
                source = folder / "source.audio"
                metadata = {"filename": job["payload"]["filename"], "source": "upload",
                            "audio_verified": False, "authorization": "user_confirmed"}
            check_cancel()
            if not source.is_file() or not 0 < source.stat().st_size <= self.limits.max_bytes:
                raise IngestionError("source_too_large", "The source audio is empty or exceeds the size limit.")
            seconds = duration(source)
            if seconds > self.limits.max_duration:
                raise IngestionError("duration_limit", "The audio exceeds the configured duration limit.")
            metadata["duration_seconds"] = seconds
            self.repository.progress(job_id, "normalizing", 10, metadata)

            def progress(manifest):
                check_cancel()
                scale = 0.45 if job["payload"].get("write_document") else 0.65 if job["payload"].get("verify") else 0.89
                stage = "transcription_completed" if manifest["state"] == "completed" else manifest["state"]
                self.repository.progress(job_id, stage, 10 + int(manifest["progress"] * scale))

            run_pipeline(source, folder / "transcription", self.settings,
                         self.transcriber, on_progress=progress, max_duration=self.limits.max_duration)
            check_cancel()
            if job["payload"].get("verify"):
                import json
                try:
                    path = verify_run(folder / "transcription", folder / "verification", self.settings,
                        self.verification_settings, self.verifier, check_cancel,
                        on_progress=lambda value: self.repository.progress(job_id, "verifying",
                            55 + int(value * .19) if job["payload"].get("write_document") else 75 + int(value * .24)))
                except JobCancelled:
                    raise
                except Exception:
                    self.repository.finish(job_id, "failed", {"code": "verification_failed",
                        "message": "Audio verification failed. The completed raw transcript remains available."})
                    return True
                review = json.loads(path.read_text())
                metadata["verification"] = {key: review[key] for key in (
                    "state", "audio_verification_performed", "coverage_fraction", "uncertain_sections", "failed_sections")}
                self.repository.progress(job_id, "verifying", 74 if job["payload"].get("write_document") else 99, metadata)
            if job["payload"].get("write_document"):
                import json
                try:
                    document_source = folder / ("verification" if job["payload"].get("verify") else "transcription")
                    doc = generate_document(document_source, folder / "document", self.writing_settings,
                        self.writer, title=metadata.get("title") or metadata.get("filename"),
                        url=job["payload"].get("url"), creator=metadata.get("channel"), check_cancel=check_cancel,
                        on_progress=lambda stage, value: self.repository.progress(job_id,
                            "document_completed" if stage == "completed" else stage, 75 + int(value * .24)))
                except JobCancelled:
                    raise
                except Exception:
                    self.repository.finish(job_id, "failed", {"code": "document_failed",
                        "message": "Document generation failed. The raw transcript remains available; check local Ollama and the document failure evidence."})
                    return True
                quality = json.loads(doc.with_name("quality.json").read_text())
                metadata["document"] = {"quality_state": quality["state"], "findings": len(quality["issues"]),
                                        "externally_fact_checked": False, "content_gate": quality.get("content_gate")}
                self.repository.progress(job_id, "document_completed", 99, metadata)
            check_cancel()
            self.repository.finish(job_id, "completed")
        except JobCancelled:
            self.repository.finish(job_id, "cancelled")
        except IngestionError as exc:
            self.repository.finish(job_id, "failed", {"code": exc.code, "message": str(exc)})
        except AudioError:
            self.repository.finish(job_id, "failed", {"code": "invalid_audio", "message": "The source has no supported, decodable audio."})
        except Exception:
            # Keep paths, signed URLs and model internals out of public API errors.
            self.repository.finish(job_id, "failed", {"code": "processing_failed", "message": "Transcription failed. Check local model availability and submit a new job to retry."})
        return True
