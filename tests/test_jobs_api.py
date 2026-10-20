import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from videomind.api import create_app
from videomind.config import Settings
from videomind.ingestion_config import IngestionSettings
from videomind.models import Transcript, Word
from videomind.repository import JobRepository, QueueFull
from videomind.services.youtube_service import IngestionError


class FakeASR:
    def transcribe(self, path, chunk):
        return Transcript(chunk, [Word(chunk.core_start + .1, chunk.core_start + .5, " hello", .9)], [], "en", 1)


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(chunk_seconds=3, overlap_seconds=1),
        IngestionSettings(storage_dir=tmp_path / "storage"), FakeASR(), start_worker=False)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://localhost") as client:
        yield client


def upload(client, audio_file, **data):
    return client.post("/api/v1/jobs", data={"authorized": "true", **data},
        files={"file": ("../../outside.wav", audio_file.read_bytes(), "audio/wav")})


def test_upload_to_existing_pipeline_and_download(app, client, audio_file, tmp_path):
    response = upload(client, audio_file)
    assert response.status_code == 202
    job = response.json()
    assert job["state"] == "queued" and response.headers["location"].endswith(job["id"])
    assert client.get(f"/api/v1/jobs/{job['id']}/transcript").status_code == 409
    assert app.state.worker.run_one() is True
    status = client.get(response.headers["location"]).json()
    assert status["state"] == "completed" and status["progress"] == 100
    assert status["metadata"]["filename"] == "outside.wav" and status["audio_verified"] is False
    assert str(tmp_path) not in json.dumps(status) and "payload" not in status
    transcript = client.get(f"/api/v1/jobs/{job['id']}/transcript").json()
    assert transcript["text"] == "hello hello hello"
    attachment = client.get(f"/api/v1/jobs/{job['id']}/transcript?format=txt")
    assert attachment.status_code == 200 and attachment.text == "hello hello hello\n"
    assert "attachment" in attachment.headers["content-disposition"]
    assert client.get(f"/api/v1/jobs/{job['id']}/transcript?kind=verified").status_code == 422
    assert client.get(f"/api/v1/jobs/{job['id']}/document").status_code == 409
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").json()["state"] == "completed"


@pytest.mark.parametrize("data", [{}, {"youtube_url": "https://evil.test"},
    {"youtube_url": "https://youtu.be/abcdefghijk", "authorized": "false"},
    {"youtube_url": "https://youtube.com/playlist?list=123"}])
def test_invalid_submission_rejected_before_queue(client, app, data):
    response = client.post("/api/v1/jobs", data={"authorized": "true", **data})
    assert response.status_code == 422 and app.state.worker.run_one() is False


def test_ambiguous_source_and_empty_upload(client, audio_file):
    assert upload(client, audio_file, youtube_url="https://youtu.be/abcdefghijk").status_code == 422
    response = client.post("/api/v1/jobs", data={"authorized": "true"}, files={"file": ("audio.wav", b"")})
    assert response.status_code == 422


def test_oversized_upload_and_chunked_body_limit(tmp_path):
    app = create_app(limits=IngestionSettings(storage_dir=tmp_path / "storage", max_bytes=10),
                     transcriber=FakeASR(), start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/api/v1/jobs", data={"authorized": "true"}, files={"file": ("a.wav", b"a" * 11)})
        assert response.status_code == 413
        response = client.post("/api/v1/jobs", content=iter([b"a" * 40000, b"a" * 40000]),
                               headers={"Content-Type": "multipart/form-data; boundary=x"})
        assert response.status_code == 413
    assert not list((tmp_path / "storage/jobs").glob("*/source.audio"))


def test_corrupt_upload_fails_gracefully(app, client):
    response = client.post("/api/v1/jobs", data={"authorized": "true"}, files={"file": ("audio.wav", b"not audio")})
    app.state.worker.run_one()
    job = client.get(response.headers["location"]).json()
    assert job["state"] == "failed" and job["error"]["code"] == "invalid_audio"
    assert job["artifacts"] == []


def test_duration_limit_checked_before_asr(tmp_path, audio_file):
    app = create_app(limits=IngestionSettings(storage_dir=tmp_path / "storage", max_duration=1),
                     transcriber=FakeASR(), start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        response = upload(client, audio_file)
        app.state.worker.run_one()
        job = client.get(response.headers["location"]).json()
        assert job["state"] == "failed" and job["error"]["code"] == "duration_limit"


def test_download_failure_persisted_without_entering_pipeline(app, client):
    def fail(*args, **kwargs):
        raise IngestionError("download_failed", "Video unavailable. Try an upload.")
    app.state.worker.downloader = fail
    response = client.post("/api/v1/jobs", data={"authorized": "true", "youtube_url": "https://youtu.be/abcdefghijk"})
    app.state.worker.run_one()
    job = client.get(response.headers["location"]).json()
    assert job["state"] == "failed" and job["error"]["code"] == "download_failed"
    assert not (app.state.worker.limits.storage_dir / "jobs" / job["id"] / "transcription").exists()


def test_youtube_download_passed_to_pipeline(app, client, audio_file):
    calls = []
    def download(url, folder, limits, authorized, check_cancel):
        calls.append((url, authorized))
        check_cancel()
        folder.mkdir()
        path = folder / "source.audio"
        path.write_bytes(audio_file.read_bytes())
        return path, {"title": "Test video", "url": url}
    app.state.worker.downloader = download
    response = client.post("/api/v1/jobs", data={"authorized": "true", "youtube_url": "https://youtu.be/abcdefghijk?si=tracking"})
    app.state.worker.run_one()
    job = client.get(response.headers["location"]).json()
    assert job["state"] == "completed" and job["metadata"]["title"] == "Test video"
    assert calls == [("https://www.youtube.com/watch?v=abcdefghijk", True)]


def test_cancel_queued_job_is_terminal(app, client, audio_file):
    response = upload(client, audio_file)
    path = response.headers["location"]
    assert client.post(path + "/cancel").json()["state"] == "cancelled"
    assert app.state.worker.run_one() is False
    assert client.post(path + "/cancel").status_code == 200
    assert client.get(path + "/transcript").status_code == 409


def test_background_job_does_not_block_api_and_cancel_is_observed(tmp_path, audio_file):
    entered, release = threading.Event(), threading.Event()
    class BlockingASR(FakeASR):
        def transcribe(self, path, chunk):
            entered.set()
            assert release.wait(timeout=10)
            return super().transcribe(path, chunk)
    app = create_app(limits=IngestionSettings(storage_dir=tmp_path / "storage"), transcriber=BlockingASR())
    with TestClient(app, base_url="http://localhost") as client:
        try:
            response = upload(client, audio_file)
            assert response.status_code == 202 and entered.wait(timeout=5)
            assert client.get(response.headers["location"]).json()["state"] == "running"
            assert client.post(response.headers["location"] + "/cancel").status_code == 202
        finally:
            release.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = client.get(response.headers["location"]).json()
            if job["state"] == "cancelled":
                break
            time.sleep(.02)
        assert job["state"] == "cancelled" and job["artifacts"] == []


def test_host_and_browser_origin_restrictions(client):
    assert client.post("/api/v1/jobs", headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.get("/docs", headers={"Host": "evil.test"}).status_code == 400


def test_unknown_job_and_path_traversal_rejected(client):
    assert client.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    assert client.get("/api/v1/jobs/not-a-uuid").status_code == 422


def test_repository_claim_limits_recovery_and_terminal_immutability(tmp_path):
    repo = JobRepository(tmp_path / "jobs.db")
    repo.add("a", {"kind": "youtube"}, 1)
    with pytest.raises(QueueFull):
        repo.add("b", {}, 1)
    assert repo.claim()["id"] == "a" and repo.claim() is None
    repo.progress("a", "transcribing", 50)
    repo.progress("a", "normalizing", 10)
    assert repo.get("a")["progress"] == 50
    repo.recover()
    assert repo.get("a")["state"] == "failed" and repo.get("a")["error"]["code"] == "interrupted"
    repo.cancel("a")
    repo.finish("a", "completed")
    assert repo.get("a")["state"] == "failed"


def test_queue_full_response_and_cleanup(tmp_path, audio_file):
    app = create_app(limits=IngestionSettings(storage_dir=tmp_path / "storage", max_jobs=1),
                     transcriber=FakeASR(), start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        assert upload(client, audio_file).status_code == 202
        assert upload(client, audio_file).status_code == 429
    assert len(list((tmp_path / "storage/jobs").iterdir())) == 1


def test_only_one_worker_can_own_storage(tmp_path):
    limits = IngestionSettings(storage_dir=tmp_path / "storage")
    first = create_app(limits=limits, transcriber=FakeASR(), start_worker=False)
    second = create_app(limits=limits, transcriber=FakeASR(), start_worker=False)
    first.state.worker.start()
    try:
        with pytest.raises(RuntimeError, match="Another worker"):
            second.state.worker.start()
    finally:
        first.state.worker.close()


@pytest.mark.real_asr
def test_real_audio_upload_through_api(tmp_path):
    source = Path("samples/generated/speech.wav")
    app = create_app(settings=Settings(model="tiny.en", language="en", local_files_only=True,
                     chunk_seconds=8, overlap_seconds=1.5),
                     limits=IngestionSettings(storage_dir=Path(os.environ.get(
                         "VIDEOMIND_TEST_API_STORAGE", str(tmp_path / "storage")))))
    with TestClient(app, base_url="http://localhost") as client:
        response = upload(client, source)
        assert response.status_code == 202
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            job = client.get(response.headers["location"]).json()
            if job["state"] in {"completed", "failed"}:
                break
            time.sleep(.05)
        assert job["state"] == "completed", job
        text = client.get(response.headers["location"] + "/transcript").json()["text"].lower()
        assert all(phrase in text for phrase in ("welcome", "solar panels", "batteries", "listening"))
        assert client.get(response.headers["location"] + "/transcript?format=txt").status_code == 200
