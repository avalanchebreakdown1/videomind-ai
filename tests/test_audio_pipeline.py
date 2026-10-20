import json
from pathlib import Path
import subprocess
import wave

import pytest

from videomind.cli import main
from videomind.config import Settings
from videomind.models import Transcript, Word
from videomind.pipeline import ALLOWED, run_pipeline, transition
from videomind.services.audio_service import AudioError, duration, normalize, run_media
from videomind.services.chunking_service import extract_chunk, plan_chunks
from videomind.services.document_service import write_json, write_text


class FakeASR:
    def __init__(self, failures=0):
        self.failures, self.calls = failures, 0

    def transcribe(self, path, chunk):
        assert path.is_file()
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary ASR error")
        word = Word(chunk.core_start + 0.1, chunk.core_start + 0.5, f" chunk{chunk.index}", 0.8)
        return Transcript(chunk, [word], [{"text": word.text}], "en", 0.9)


@pytest.mark.integration
def test_real_normalization_and_chunk_samples(audio_file, tmp_path):
    target = tmp_path / "normalized.wav"
    seconds = normalize(audio_file, target, 60)
    assert seconds == pytest.approx(7, abs=1 / 16000)
    with wave.open(str(target)) as handle:
        assert (handle.getnchannels(), handle.getframerate(), handle.getsampwidth()) == (1, 16000, 2)
    chunks = plan_chunks(seconds, Settings(chunk_seconds=3, overlap_seconds=1))
    assert len(chunks) == 3
    for chunk in chunks:
        path = tmp_path / f"chunk{chunk.index}.wav"
        extract_chunk(target, path, chunk, 60)
        with wave.open(str(path)) as handle:
            assert handle.getnframes() == round((chunk.audio_end - chunk.audio_start) * 16000)
            actual_start = handle.readframes(16)
        with wave.open(str(target)) as original:
            original.setpos(round(chunk.audio_start * 16000))
            assert actual_start == original.readframes(16)


@pytest.mark.integration
def test_full_pipeline_mock_asr(audio_file, tmp_path):
    folder = tmp_path / "result"
    states = []
    output = run_pipeline(audio_file, folder, Settings(chunk_seconds=3, overlap_seconds=1),
                          FakeASR(), on_progress=lambda m: states.append((m["state"], m["progress"])))
    assert output.read_text() == "chunk0 chunk1 chunk2\n"
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["state"] == "completed" and manifest["progress"] == 100
    assert manifest["chunks_completed"] == 3 and manifest["audio_verified"] is False
    assert len(list((folder / "raw_chunks").glob("*.json"))) == 3
    assert not list((folder / "audio_chunks").glob("*.wav"))
    assert states[0] == ("created", 0) and states[-1] == ("completed", 100)
    assert [p for _, p in states] == sorted(p for _, p in states)
    data = json.loads((folder / "raw_transcript.json").read_text())
    assert data["text"] == "chunk0 chunk1 chunk2" and len(data["words"]) == 3


@pytest.mark.integration
def test_retry_then_success(audio_file, tmp_path):
    folder = tmp_path / "retry"
    fake = FakeASR(failures=1)
    run_pipeline(audio_file, folder, Settings(), fake, keep_chunks=True)
    assert fake.calls == 2
    assert json.loads((folder / "manifest.json").read_text())["retry_count"] == 1
    assert len(list((folder / "audio_chunks").glob("*.wav"))) == 1


@pytest.mark.integration
def test_permanent_failure_preserves_state_and_no_final_txt(audio_file, tmp_path):
    folder = tmp_path / "failure"
    fake = FakeASR(failures=20)
    with pytest.raises(RuntimeError, match="temporary ASR error"):
        run_pipeline(audio_file, folder, Settings(asr_retries=1), fake)
    assert fake.calls == 2
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["state"] == "failed" and manifest["progress"] < 100
    assert manifest["error"]["type"] == "RuntimeError"
    assert not (folder / "raw_transcript.txt").exists()


@pytest.mark.integration
def test_corrupt_file_records_failure(tmp_path):
    source = tmp_path / "bad.wav"
    source.write_bytes(b"not audio")
    with pytest.raises(AudioError):
        run_pipeline(source, tmp_path / "failed", Settings(), FakeASR())
    manifest = json.loads((tmp_path / "failed/manifest.json").read_text())
    assert manifest["state"] == "failed"


@pytest.mark.integration
def test_local_playlist_cannot_reference_other_files(audio_file, tmp_path):
    playlist = tmp_path / "disguised.wav"
    playlist.write_text(f"ffconcat version 1.0\nfile '{audio_file}'\n")
    with pytest.raises(AudioError):
        duration(playlist)


@pytest.mark.integration
def test_normalization_duration_limit(audio_file, tmp_path):
    with pytest.raises(AudioError, match="duration limit"):
        normalize(audio_file, tmp_path / "limited.wav", 60, max_duration=2)
    assert not (tmp_path / "limited.wav").exists()


def test_never_overwrite_existing_directory(audio_file, tmp_path):
    folder = tmp_path / "existing"
    folder.mkdir()
    marker = folder / "keep.txt"
    marker.write_text("unchanged")
    with pytest.raises(FileExistsError):
        run_pipeline(audio_file, folder, Settings(), FakeASR())
    assert marker.read_text() == "unchanged" and not (folder / "manifest.json").exists()


def test_missing_input_creates_no_run(tmp_path):
    with pytest.raises(ValueError):
        run_pipeline(tmp_path / "missing", tmp_path / "run", Settings(), FakeASR())
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("old", ALLOWED)
@pytest.mark.parametrize("new", ALLOWED)
def test_state_transition_matrix(old, new):
    manifest = {"state": old}
    if new in ALLOWED[old]:
        transition(manifest, new)
        assert manifest["state"] == new
    else:
        with pytest.raises(ValueError):
            transition(manifest, new)
        assert manifest["state"] == old


def test_atomic_exports_unicode_and_json(tmp_path):
    path = tmp_path / "document.txt"
    write_text(path, "科学 café\n")
    assert path.read_bytes().decode("utf-8") == "科学 café\n"
    write_json(tmp_path / "data.json", {"text": "科学"})
    assert json.loads((tmp_path / "data.json").read_text()) == {"text": "科学"}
    assert not list(tmp_path.glob(".tmp-*"))


def test_media_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(AudioError, match="Media tool failed"):
        run_media(["ffmpeg"], 1)


def test_missing_media_tool(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not installed")
    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(AudioError, match="ffmpeg not installed"):
        run_media(["ffmpeg"], 1)


@pytest.mark.integration
def test_interruption_preserves_completed_chunk_evidence(audio_file, tmp_path):
    class InterruptedASR(FakeASR):
        def transcribe(self, path, chunk):
            if chunk.index == 1:
                raise KeyboardInterrupt()
            return super().transcribe(path, chunk)

    folder = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        run_pipeline(audio_file, folder, Settings(chunk_seconds=3, overlap_seconds=1), InterruptedASR())
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["state"] == "failed" and manifest["chunks_completed"] == 1
    assert manifest["error"]["type"] == "KeyboardInterrupt"
    assert (folder / "raw_chunks/000000.json").is_file()
    assert not (folder / "raw_transcript.txt").exists()
    assert not list((folder / "audio_chunks").glob("*.wav"))


@pytest.mark.integration
def test_empty_recognition_has_explicit_warning(audio_file, tmp_path):
    class EmptyASR:
        def transcribe(self, path, chunk):
            return Transcript(chunk, [], [], "en", 0.1)

    folder = tmp_path / "empty"
    run_pipeline(audio_file, folder, Settings(), EmptyASR())
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["state"] == "completed"
    assert "No speech recognized" in manifest["warnings"][-1]
    assert (folder / "raw_transcript.txt").read_text() == "\n"


def test_cli_invalid_arguments_and_source(tmp_path, capsys):
    assert main([str(tmp_path / "missing"), "--output-dir", str(tmp_path / "run")]) == 1
    assert "Transcription failed" in capsys.readouterr().err
    assert main([str(tmp_path / "missing"), "--output-dir", str(tmp_path / "run"),
                 "--chunk-seconds", "nan"]) == 1
