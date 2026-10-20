from dataclasses import replace
import json
from pathlib import Path

import pytest

from videomind.cli import main
from videomind.config import Settings
from videomind.models import Chunk, Transcript, Word
from videomind.pipeline import run_pipeline
from videomind.services.verification_service import (
    compare_candidates, normalized_token, primary_artifacts, require_distinct,
    select_sections, sha256, verify_run,
)
from videomind.verification_config import VerificationSettings


WORDS = [Word(.1, .5, " The", .95), Word(1, 1.5, " cat", .3), Word(2.1, 2.5, " sat.", .95)]


class Primary:
    def transcribe(self, path, chunk):
        return Transcript(chunk, WORDS, [{"start": 0, "end": 3, "text": " The cat sat."}], "en", .99)


class Secondary:
    def __init__(self, replacements=None, probability=.95, fail=False):
        self.calls = []
        self.replacements = replacements or ["cat", "cat"]
        self.probability, self.fail = probability, fail

    def transcribe(self, path, chunk):
        assert path.is_file()
        self.calls.append(chunk)
        if self.fail:
            raise RuntimeError("controlled audio ASR failure")
        words = [replace(word, probability=self.probability) for word in WORDS]
        words[1] = replace(words[1], text=" " + self.replacements[min(len(self.calls) - 1, 1)])
        words = [word for word in words if chunk.audio_start <= word.start and word.end <= chunk.audio_end]
        return Transcript(chunk, words, [{"text": "".join(w.text for w in words)}], "en", .99)


@pytest.fixture
def primary_run(audio_file, tmp_path):
    folder = tmp_path / "primary"
    run_pipeline(audio_file, folder, Settings(model="primary-test"), Primary())
    return folder


def config(**overrides):
    return VerificationSettings(model="secondary-test", section_seconds=2, context_seconds=0,
                                 recheck_context_seconds=1, max_sections=1, **overrides)


def source_hashes(run):
    return {str(path.relative_to(run)): sha256(path) for path in primary_artifacts(run) + [run / "normalized.wav"]}


@pytest.mark.parametrize("token,expected", [(" Cat.", "Cat"), ("1.5", "1.5"), ("-5", "-5"),
    ("1,000", "1,000"), ("10%", "10%"), ("日本語。", "日本語")])
def test_comparison_normalization_preserves_meaningful_symbols(token, expected):
    assert normalized_token(token) == expected


def test_numbers_and_negation_are_disagreements():
    for a, b in [("1.5", "15"), ("-5", "5"), ("can", "cannot")]:
        assert compare_candidates([Word(0, 1, a, .9)], [Word(0, 1, b, .9)], .65)["needs_review"]


@pytest.mark.parametrize("primary,candidate", [("mW", "MW"), ("ms", "Ms"), ("Co", "CO"),
    ("10³", "103"), ("x²", "x2"), ("H₂", "H2"), (".5", "5"), ("x′", "x"), ("f(x)", "f(x"),
    ("n!", "n"), ("x:", "x"), ("x?", "x"), ("10...", "10")])
def test_scientific_notation_changes_are_never_supported_as_equal(primary, candidate):
    result = compare_candidates([Word(0, 1, primary, .99)], [Word(0, 1, candidate, .99)], .65)
    assert result["needs_review"] and result["uncertain_indices"] == [0]
    assert not result["supported_indices"]


def test_canonical_unicode_and_prose_full_stop_still_match():
    assert normalized_token("cafe\u0301") == normalized_token("café")
    assert normalized_token(" voltage.") == normalized_token("voltage")
    assert normalized_token("The") != normalized_token("the")


@pytest.mark.parametrize("mode", ["substitution", "omission", "insertion"])
def test_controlled_candidate_disagreements(mode):
    candidate = list(WORDS)
    if mode == "substitution":
        candidate[1] = replace(candidate[1], text=" dog")
    elif mode == "omission":
        candidate.pop(1)
    else:
        candidate.insert(1, Word(.6, .8, " big", .95))
    comparison = compare_candidates(WORDS, candidate, .65)
    assert comparison["needs_review"] and len(comparison["disagreements"]) == 1
    assert comparison["disagreements"][0]["operation"] == {"substitution": "replace", "omission": "delete", "insertion": "insert"}[mode]


def test_equal_words_with_low_secondary_confidence_are_uncertain():
    result = compare_candidates(WORDS, [replace(w, probability=.2) for w in WORDS], .65)
    assert result["uncertain_indices"] == [0, 1, 2] and result["needs_review"]


def test_matching_text_at_different_audio_time_is_not_supported():
    comparison = compare_candidates([Word(1, 2, "same", .9)], [Word(10, 11, "same", .99)], .65)
    assert comparison["supported_indices"] == [] and comparison["uncertain_indices"] == [0]
    assert comparison["disagreements"][0]["operation"] == "timing_mismatch"


def test_same_checkpoint_rejected_including_aliases_and_weight_copies(tmp_path):
    with pytest.raises(ValueError, match="different ASR"):
        require_distinct("tiny.en", "Systran/faster-whisper-tiny.en", str(tmp_path), str(tmp_path))
    for name in ("first", "second"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "model.bin").write_bytes(b"same-model-weights")
    with pytest.raises(ValueError):
        require_distinct(str(tmp_path / "first"), str(tmp_path / "second"), "unused", "unused")


def test_distinct_local_weights_with_identical_folder_names_are_allowed(tmp_path):
    paths = [tmp_path / "one/model", tmp_path / "two/model"]
    for i, path in enumerate(paths):
        path.mkdir(parents=True)
        (path / "model.bin").write_bytes(f"distinct checkpoint {i}".encode())
    first, second = require_distinct(str(paths[0]), str(paths[1]), "unused", "unused")
    assert first["weights_sha256"] != second["weights_sha256"]


def test_no_recheck_when_disabled(primary_run, tmp_path):
    engine = Secondary(["dog", "dog"])
    verify_run(primary_run, tmp_path / "no-recheck", Settings(), replace(config(), recheck=False), engine)
    assert len(engine.calls) == 1


def test_no_identical_crop_recheck_without_additional_context(primary_run, tmp_path):
    engine = Secondary(["dog", "dog"])
    path = verify_run(primary_run, tmp_path / "no-context", Settings(),
        VerificationSettings(model="secondary-test", section_seconds=10), engine)
    report = json.loads(path.read_text())
    assert len(engine.calls) == 1 and report["sections"][0]["status"] == "uncertain"
    assert "recheck_skipped" in report["sections"][0]


@pytest.mark.parametrize("values", [{"section_seconds": float("nan")}, {"section_seconds": 1000},
    {"context_seconds": -1}, {"context_seconds": 10, "recheck_context_seconds": 2},
    {"word_threshold": 0}, {"max_sections": 0}, {"gap_seconds": 0}, {"model": ""}])
def test_invalid_verification_configuration(values):
    with pytest.raises(ValueError):
        VerificationSettings(**values)


def test_environment_settings(monkeypatch):
    monkeypatch.setenv("VIDEOMIND_VERIFY_MODEL", "base.en")
    monkeypatch.setenv("VIDEOMIND_VERIFY_RECHECK", "false")
    settings = VerificationSettings.from_env()
    assert settings.model == "base.en" and not settings.recheck
    monkeypatch.setenv("VIDEOMIND_VERIFY_RECHECK", "perhaps")
    with pytest.raises(ValueError):
        VerificationSettings.from_env()


def test_suspicion_selection_metrics_repetition_gap_and_boundary():
    words = [Word(0, .5, " no", .9), Word(.6, 1, " no", .9), Word(20, 21, " yes", .2)]
    chunks = [Chunk(0, 0, 10, 0, 12), Chunk(1, 10, 30, 8, 30)]
    raw = [{"chunk": {"audio_start": 0, "core_start": 0, "core_end": 30}, "words": [1],
            "segments": [{"start": 4, "end": 5, "avg_logprob": -2}]}]
    sections, omitted = select_sections(words, raw, chunks, 30, VerificationSettings(section_seconds=5))
    reasons = {reason for section in sections for reason in section["reasons"]}
    assert {"low_word_probability", "repetition", "untranscribed_gap", "chunk_boundary", "suspicious_segment_metrics"} <= reasons
    assert not omitted
    assert all(section["end"] - section["start"] <= 5 for section in sections)


def test_verification_agreement_keeps_original_bytes_and_unchecked_scope(primary_run, tmp_path):
    before = source_hashes(primary_run)
    engine = Secondary()
    output = tmp_path / "review"
    report_path = verify_run(primary_run, output, Settings(), config(), engine)
    report = json.loads(report_path.read_text())
    assert report["state"] == "completed" and report["audio_verification_performed"]
    assert not report["audio_verified"] and not report["all_audio_checked"]
    assert report["coverage_fraction"] == pytest.approx(2 / 7)
    assert report["omitted_candidate_sections"] > 0
    assert len(engine.calls) == 1
    result = json.loads((output / "verified_transcript.json").read_text())
    assert result["text"] == "The cat sat."
    assert [word["verification_status"] for word in result["words"]] == ["supported_by_second_asr", "supported_by_second_asr", "not_checked"]
    assert source_hashes(primary_run) == before
    assert report["source_artifacts_sha256"] == {key: value for key, value in before.items() if key != "normalized.wav"}
    document = json.loads((output / "document_source.json").read_text())
    assert document["text"] == "The cat sat." and not document["fact_checked"]
    assert "document_source.txt" in report["artifacts"]


@pytest.mark.parametrize("replacements", [["dog", "dog"], ["dog", "cat"], ["dog", "fox"]])
def test_disagreements_are_reprocessed_but_never_silently_corrected(primary_run, tmp_path, replacements):
    before = source_hashes(primary_run)
    engine = Secondary(replacements)
    report = json.loads(verify_run(primary_run, tmp_path / "review", Settings(), config(), engine).read_text())
    assert len(engine.calls) == 2 and engine.calls[1].audio_end > engine.calls[0].audio_end
    assert report["sections"][0]["status"] == "uncertain"
    assert report["sections"][0]["passes"][0]["comparison"]["disagreements"][0]["candidate_text"] == "dog"
    derived = json.loads((tmp_path / "review/verified_transcript.json").read_text())
    assert derived["text"] == "The cat sat." and "[uncertain: cat]" in derived["annotated_text"]
    assert "dog" not in derived["text"]
    assert (tmp_path / "review/sections/000000/pass2.json").exists()
    assert not list((tmp_path / "review").rglob("*.wav"))
    assert source_hashes(primary_run) == before


def test_bounded_retries_and_failed_audio_review_do_not_claim_success(primary_run, tmp_path):
    engine = Secondary(fail=True)
    path = verify_run(primary_run, tmp_path / "failed", Settings(asr_retries=1), config(), engine)
    result = json.loads(path.read_text())
    assert len(engine.calls) == 2
    assert result["state"] == "completed_with_errors" and result["failed_sections"] == 1
    assert not result["audio_verification_performed"] and result["coverage_fraction"] == 0
    assert result["word_counts"]["uncertain"] == 2
    assert (tmp_path / "failed/sections/000000/pass1-attempts.json").exists()


def test_missing_words_are_flagged_without_inserting_candidate(primary_run, tmp_path):
    class ExtraWord(Secondary):
        def transcribe(self, path, chunk):
            result = super().transcribe(path, chunk)
            return replace(result, words=[result.words[0], Word(.6, .9, " big", .99), *result.words[1:]])
    path = verify_run(primary_run, tmp_path / "extra", Settings(), config(), ExtraWord())
    report = json.loads(path.read_text())
    assert report["uncertain_sections"] == 1
    assert "big" not in json.loads((tmp_path / "extra/verified_transcript.json").read_text())["text"]


def test_invalid_secondary_timestamps_become_uncertainty(primary_run, tmp_path):
    class Invalid(Secondary):
        def transcribe(self, path, chunk):
            return Transcript(chunk, [Word(-100, 200, " invalid", .9)], [], "en", 1)
    report = json.loads(verify_run(primary_run, tmp_path / "invalid", Settings(), config(), Invalid()).read_text())
    assert report["failed_sections"] == 1 and not report["audio_verification_performed"]


def test_no_speech_in_both_passes_does_not_prove_silence(primary_run, tmp_path):
    from videomind.services.document_service import write_json, write_text
    # Build a consistent empty primary fixture, without altering any user's transcript.
    raw = json.loads((primary_run / "raw_chunks/000000.json").read_text())
    raw.update(words=[], segments=[])
    write_json(primary_run / "raw_chunks/000000.json", raw)
    write_json(primary_run / "raw_transcript.json", {"text": "", "words": []})
    write_text(primary_run / "raw_transcript.txt", "\n")
    class Empty:
        def transcribe(self, path, chunk):
            return Transcript(chunk, [], [], "en", .1)
    result = json.loads(verify_run(primary_run, tmp_path / "empty", Settings(), config(), Empty()).read_text())
    assert result["sections"][0]["status"] == "uncertain"
    assert result["sections"][0]["passes"][0]["comparison"]["empty_both"]


def test_reject_modified_primary_evidence(primary_run, tmp_path):
    (primary_run / "raw_transcript.txt").write_text("Changed externally\n")
    with pytest.raises(ValueError, match="do not match"):
        verify_run(primary_run, tmp_path / "review", Settings(), config(), Secondary())
    assert not (tmp_path / "review").exists()


def test_never_write_into_primary_run_or_existing_output(primary_run, tmp_path):
    with pytest.raises(ValueError, match="outside"):
        verify_run(primary_run, primary_run / "verification", Settings(), config(), Secondary())
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        verify_run(primary_run, output, Settings(), config(), Secondary())
    assert marker.read_text() == "keep"


def test_interruption_keeps_evidence_and_primary_artifacts(primary_run, tmp_path):
    before = source_hashes(primary_run)
    class Interrupt(Secondary):
        def transcribe(self, path, chunk):
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        verify_run(primary_run, tmp_path / "interrupted", Settings(), config(), Interrupt())
    report = json.loads((tmp_path / "interrupted/verification.json").read_text())
    assert report["state"] == "failed" and source_hashes(primary_run) == before
    assert not (tmp_path / "interrupted/verified_transcript.txt").exists()


def test_cooperative_cancellation_is_not_swallowed_as_asr_error(primary_run, tmp_path):
    before = source_hashes(primary_run)
    calls = [0]
    def cancel():
        calls[0] += 1
        if calls[0] >= 2:
            raise RuntimeError("controlled cancellation")
    with pytest.raises(RuntimeError, match="controlled cancellation"):
        verify_run(primary_run, tmp_path / "cancelled", Settings(), config(), Secondary(), check_cancel=cancel)
    assert json.loads((tmp_path / "cancelled/verification.json").read_text())["state"] == "failed"
    assert source_hashes(primary_run) == before


def test_cli_verify_dispatch_and_same_model_error(primary_run, tmp_path, capsys):
    assert main(["verify", "--run-dir", str(primary_run), "--output-dir", str(tmp_path / "review"),
                 "--model", "primary-test"]) == 1
    assert "different ASR checkpoint" in capsys.readouterr().err


@pytest.mark.real_asr
def test_real_second_checkpoint_on_local_audio(tmp_path):
    run = Path("runs/smoke-final")
    before = source_hashes(run)
    report_path = verify_run(run, tmp_path / "real-review", Settings(local_files_only=True),
                             VerificationSettings(model="small"))
    report = json.loads(report_path.read_text())
    assert report["state"] == "completed" and report["audio_verification_performed"]
    assert report["all_audio_checked"] and report["coverage_fraction"] == pytest.approx(1)
    assert report["secondary_checkpoint"]["weights_sha256"] != report["primary_checkpoint"]["weights_sha256"]
    assert report["word_counts"]["supported_by_second_asr"] > 20
    assert source_hashes(run) == before
