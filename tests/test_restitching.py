from dataclasses import asdict
import json

import pytest

from videomind.cli import main
from videomind.config import Settings
from videomind.models import Transcript, Word
from videomind.pipeline import run_pipeline
from videomind.services.document_service import write_json, write_text
from videomind.services.restitching_service import restitch_run
from videomind.services.stitching_service import LEGACY_VERSION, STITCHING_VERSION, stitch
from videomind.services.verification_service import load_primary, primary_artifacts, sha256


@pytest.fixture
def legacy_run(audio_file, tmp_path):
    class ASR:
        def transcribe(self, path, chunk):
            if chunk.index == 0:
                words = [Word(3.1, 3.4, " voltage", .9)]
            elif chunk.index == 1:
                words = [Word(2.6, 2.9, " voltage", .9)]
            else:
                words = []
            return Transcript(chunk, words, [], "en", .99)
    run = tmp_path / "original"
    run_pipeline(audio_file, run, Settings(chunk_seconds=3, overlap_seconds=1, model="primary-test"), ASR())
    manifest, raw, _, chunks, raw_chunks, _ = load_primary(run)
    from videomind.models import Chunk
    results = [Transcript(Chunk(**r["chunk"]), [Word(**w) for w in r["words"]], [], "en", .99) for r in raw_chunks]
    old_words = stitch(results, chunks, version=LEGACY_VERSION)
    # Make a consistent pre-fix fixture. Never mutate an actual user's run.
    manifest.pop("stitching_version")
    raw.update(text="", words=[asdict(w) for w in old_words])
    raw.pop("stitching_issues", None)
    write_json(run / "manifest.json", manifest)
    write_json(run / "raw_transcript.json", raw)
    write_text(run / "raw_transcript.txt", "\n")
    (run / "stitching.json").unlink()
    return run


def hashes(run):
    return {str(path.relative_to(run)): sha256(path) for path in primary_artifacts(run) + [run / "normalized.wav"]}


def test_old_transcripts_still_validate_and_rebuild_separately(legacy_run, tmp_path):
    before = hashes(legacy_run)
    assert load_primary(legacy_run)[1]["text"] == ""
    path = restitch_run(legacy_run, tmp_path / "rebuilt")
    assert path.read_text() == "voltage\n"
    assert hashes(legacy_run) == before
    manifest, raw, *_ = load_primary(path.parent)
    assert manifest["stitching_version"] == STITCHING_VERSION
    assert raw["text"] == "voltage" and raw["stitching_issues"]
    audit = json.loads((path.parent / "restitching.json").read_text())
    assert audit["original_artifacts_unchanged"] and audit["text_changed"]
    assert audit["source_artifacts_sha256"] == before
    assert sha256(path.parent / "normalized.wav") == before["normalized.wav"]
    for original in (legacy_run / "raw_chunks").glob("*.json"):
        assert sha256(path.parent / "raw_chunks" / original.name) == sha256(original)


def test_new_run_requires_stitching_evidence(legacy_run, tmp_path):
    path = restitch_run(legacy_run, tmp_path / "rebuilt")
    (path.parent / "stitching.json").unlink()
    with pytest.raises(ValueError, match="Missing versioned stitching evidence"):
        load_primary(path.parent)


def test_rebuild_refuses_overwrite_and_inside_source(legacy_run, tmp_path):
    before = hashes(legacy_run)
    with pytest.raises(ValueError, match="outside"):
        restitch_run(legacy_run, legacy_run / "nested")
    with pytest.raises(FileExistsError):
        restitch_run(legacy_run, tmp_path)
    assert hashes(legacy_run) == before


def test_restitch_cli(legacy_run, tmp_path):
    assert main(["restitch", "--run-dir", str(legacy_run), "--output-dir", str(tmp_path / "rebuilt")]) == 0
    assert (tmp_path / "rebuilt/raw_transcript.txt").read_text() == "voltage\n"


def test_unreviewed_boundary_ambiguity_remains_flagged(legacy_run, tmp_path):
    from videomind.verification_config import VerificationSettings
    from videomind.services.verification_service import verify_run
    class EmptyAudioPass:
        def transcribe(self, path, chunk):
            return Transcript(chunk, [], [], "en", .99)
    rebuilt = restitch_run(legacy_run, tmp_path / "rebuilt").parent
    review = tmp_path / "review"
    verify_run(rebuilt, review, Settings(), VerificationSettings(model="second-test", section_seconds=2,
        context_seconds=0, recheck_context_seconds=1, max_sections=1, recheck=False), EmptyAudioPass())
    result = json.loads((review / "verified_transcript.json").read_text())
    assert result["words"][0]["verification_status"] == "uncertain"
    assert not result["words"][0]["audio_reviewed"]
    assert any(span["status"] == "unreviewed_stitching_issue" for span in result["uncertain_audio_spans"])
