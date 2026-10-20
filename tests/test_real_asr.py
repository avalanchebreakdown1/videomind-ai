import json
import os
from pathlib import Path

import pytest

from videomind.cli import main


@pytest.mark.real_asr
def test_local_speech_through_real_cli(tmp_path, monkeypatch):
    source = Path(os.environ.get("VIDEOMIND_TEST_AUDIO", "samples/generated/speech.wav"))
    assert source.is_file(), "Run python scripts/create_sample.py first"
    output = Path(os.environ.get("VIDEOMIND_TEST_OUTPUT", str(tmp_path / "real-asr")))
    monkeypatch.setenv("VIDEOMIND_LOCAL_FILES_ONLY", "true")
    assert main([str(source), "--output-dir", str(output), "--model", "tiny.en",
                 "--language", "en", "--chunk-seconds", "8", "--overlap-seconds", "1.5"]) == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["state"] == "completed" and manifest["chunks_total"] >= 2
    text = (output / "raw_transcript.txt").read_text().lower()
    # Integration acceptance, not a claim of word-perfect transcription.
    for phrase in ("welcome", "solar panels", "batteries", "listening"):
        assert phrase in text, f"Expected recognizable speech {phrase!r}, got {text!r}"
    assert text.count("solar panels") == 2  # Keep the intentional repeated subject.
    assert manifest["audio_verified"] is False
