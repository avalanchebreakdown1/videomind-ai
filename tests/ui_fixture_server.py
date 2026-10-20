"""Opt-in browser-test server. Never imported by the production app factory."""
import json
import os
from pathlib import Path
import shutil
import time
import wave

from videomind.api import create_app
from videomind.config import Settings
from videomind.ingestion_config import IngestionSettings
from videomind.models import Transcript, Word
from videomind.services.ollama_service import OllamaError
from videomind.services.youtube_service import IngestionError

TEXT = "Under the stated conditions, the detector receives .5 mW over 2 cm²."
root = Path(os.environ.get("VIDEOMIND_UI_TEST_STORAGE", "/tmp/videomind-ui-integration"))
root.mkdir(parents=True, exist_ok=True)
audio = root / "fixture.wav"
with wave.open(str(audio), "wb") as handle:
    handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(8000)
    handle.writeframes(b"\0\0" * 16000)


class ASR:
    def transcribe(self, path, chunk):
        time.sleep(.8)
        return Transcript(chunk, [Word(.1, 1.5, TEXT, .99)], [], "en", 1)


class Writer:
    def metadata(self):
        return {"model": "browser-fixture", "digest": "controlled-offline"}

    def chat(self, request):
        data = json.loads(request["messages"][1]["content"].split("\nUNTRUSTED_DATA_JSON:\n")[1])
        time.sleep(.8)
        if data["source_title"] == "document-failure.wav":
            raise OllamaError("Controlled writing failure")
        result = {"sections": [{"heading": "Optical measurements", "explanation": "The detector receives .5 mW over 2 cm² under the specified conditions.", "code_examples": []}], "corrections": []}
        return {"done": True, "message": {"content": json.dumps(result)}}


def download(url, destination, limits, authorized, check_cancel):
    check_cancel()
    if "AAAAAAAAAAA" in url:
        raise IngestionError("download_failed", "This video is unavailable. Try an audio upload.")
    destination.mkdir(parents=True)
    target = destination / "source.audio"
    shutil.copyfile(audio, target)
    return target, {"title": "Optics lesson — browser integration test", "channel": "Offline fixture", "url": url}


app = create_app(Settings(model="browser-fixture", chunk_seconds=5, overlap_seconds=.5),
                 IngestionSettings(storage_dir=root / "jobs-data"), ASR(), download,
                 writer=Writer())
