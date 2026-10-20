from dataclasses import replace
import json

from fastapi.testclient import TestClient

from videomind.api import create_app
from videomind.config import Settings
from videomind.ingestion_config import IngestionSettings
from videomind.models import Transcript, Word
from videomind.verification_config import VerificationSettings


class Primary:
    def transcribe(self, path, chunk):
        return Transcript(chunk, [Word(.1, .5, " The", .9), Word(1, 1.5, " cat.", .2)], [], "en", .99)


class Secondary:
    def transcribe(self, path, chunk):
        return Transcript(chunk, [Word(.1, .5, " The", .99), Word(1, 1.5, " dog.", .99)], [], "en", .99)


def make_app(tmp_path):
    return create_app(settings=Settings(model="primary-test"),
                      limits=IngestionSettings(storage_dir=tmp_path / "storage"),
                      transcriber=Primary(), verifier=Secondary(), start_worker=False,
                      verification_settings=VerificationSettings(model="secondary-test", section_seconds=10))


def submit(client, audio_file):
    return client.post("/api/v1/jobs", data={"authorized": "true", "verify": "true"},
                       files={"file": ("speech.wav", audio_file.read_bytes(), "audio/wav")})


def test_job_verification_and_evidence_download(tmp_path, audio_file):
    app = make_app(tmp_path)
    with TestClient(app, base_url="http://localhost") as client:
        response = submit(client, audio_file)
        assert response.status_code == 202
        location = response.headers["location"]
        assert client.get(location + "/verification").status_code == 409
        app.state.worker.run_one()
        job = client.get(location).json()
        assert job["state"] == "completed" and job["progress"] == 100
        assert job["verification"]["audio_verification_performed"]
        assert job["verification"]["uncertain_sections"] == 1
        assert "verification.json" in job["artifacts"] and not job["audio_verified"]
        raw = client.get(location + "/transcript").json()
        reviewed = client.get(location + "/transcript?kind=verified").json()
        assert raw["text"] == reviewed["text"] == "The cat."
        assert "[uncertain: cat.]" in reviewed["annotated_text"]
        report = client.get(location + "/verification").json()
        assert report["raw_artifacts_unchanged"] and report["secondary_checkpoint"]["model"] == "secondary-test"
        assert str(tmp_path) not in json.dumps(report)
        attachment = client.get(location + "/transcript?kind=verified&format=txt")
        assert attachment.status_code == 200 and "uncertain" in attachment.text
        assert "verified-transcript" in attachment.headers["content-disposition"]
        document_source = client.get(location + "/document-source").json()
        assert document_source["text"] == "The cat." and not document_source["fact_checked"]
        assert "[uncertain: cat.]" in document_source["annotated_text"]
        assert client.get(location + "/document-source?format=txt").status_code == 200
        assert client.get(location + "/document-source?format=docx").status_code == 422


def test_verification_setup_failure_keeps_raw_transcript_accessible(tmp_path, audio_file, monkeypatch):
    import videomind.worker as module
    def fail(*args, **kwargs):
        raise RuntimeError("controlled verification setup failure")
    monkeypatch.setattr(module, "verify_run", fail)
    app = make_app(tmp_path)
    with TestClient(app, base_url="http://localhost") as client:
        response = submit(client, audio_file)
        app.state.worker.run_one()
        location = response.headers["location"]
        status = client.get(location).json()
        assert status["state"] == "failed" and status["error"]["code"] == "verification_failed"
        assert "raw_transcript.txt" in status["artifacts"]
        assert client.get(location + "/transcript?format=txt").text == "The cat.\n"
        assert client.get(location + "/transcript?kind=verified").status_code == 409


def test_same_model_is_rejected_before_submission(tmp_path, audio_file):
    app = create_app(settings=Settings(model="tiny.en"),
                      limits=IngestionSettings(storage_dir=tmp_path / "storage"),
                      verification_settings=VerificationSettings(model="tiny.en"), start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        response = submit(client, audio_file)
        assert response.status_code == 422 and response.json()["error"]["code"] == "same_verification_model"


def test_secondary_asr_failure_is_reported_without_false_verified_claim(tmp_path, audio_file):
    class Failing:
        def transcribe(self, path, chunk):
            raise RuntimeError("ASR unavailable")
    app = make_app(tmp_path)
    app.state.worker.verifier = Failing()
    with TestClient(app, base_url="http://localhost") as client:
        response = submit(client, audio_file)
        app.state.worker.run_one()
        location = response.headers["location"]
        job = client.get(location).json()
        assert job["state"] == "completed" and job["verification"]["state"] == "completed_with_errors"
        assert not job["verification"]["audio_verification_performed"]
        report = client.get(location + "/verification").json()
        assert not report["all_audio_checked"] and report["failed_sections"] == 1
        assert "[uncertain:" in client.get(location + "/transcript?kind=verified").json()["annotated_text"]
