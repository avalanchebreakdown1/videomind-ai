import threading
from fastapi.testclient import TestClient

from test_direct_rewrite import DirectModel
from test_writing import MeasurementASR
from videomind.api import create_app
from videomind.config import Settings
from videomind.ingestion_config import IngestionSettings


def test_health_and_raw_preview_available_while_writing(tmp_path, audio_file, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    class PausedWriter(DirectModel):
        def chat(self, request):
            entered.set()
            assert release.wait(10)
            return super().chat(request)
    app = create_app(Settings(model="fixture"), IngestionSettings(storage_dir=tmp_path / "storage"),
                     MeasurementASR(), writer=PausedWriter(), start_worker=False)
    observed = []
    original_progress = app.state.repository.progress
    def record(job_id, stage, value, metadata=None):
        observed.append(stage)
        return original_progress(job_id, stage, value, metadata)
    monkeypatch.setattr(app.state.repository, "progress", record)
    with TestClient(app, base_url="http://localhost") as client:
        health = client.get("/api/v1/health").json()
        assert health["status"] == "ok" and not health["audio_verification_default"]
        response = client.post("/api/v1/jobs", data={"authorized": "true", "write_document": "true"},
                               files={"file": ("lesson.wav", audio_file.read_bytes(), "audio/wav")})
        location = response.headers["location"]
        assert client.get(location + "/transcript").status_code == 409
        thread = threading.Thread(target=app.state.worker.run_one)
        thread.start()
        try:
            assert entered.wait(10)
            status = client.get(location).json()
            assert status["state"] == "running" and "raw_transcript.json" in status["artifacts"]
            assert client.get(location + "/transcript").status_code == 200
            assert client.get(location + "/document").status_code == 409
        finally:
            release.set(); thread.join(10)
        assert not thread.is_alive()
        assert client.get(location).json()["state"] == "completed"
        assert "transcription_completed" in observed and "completed" not in observed
