import json
from pathlib import Path

import pytest

from videomind.benchmark_cli import main
from videomind.services.benchmark_service import evaluate, sha256, word_errors


FIXTURES = Path(__file__).parent / "fixtures" / "benchmark"


def inputs():
    return tuple((FIXTURES / name).read_bytes() for name in
                 ("reference.json", "transcript.txt", "notes.txt"))


def review_for(reference, notes):
    # Controlled annotations test the contract; these are NOT educator review.
    return {
        "reviewer": "synthetic test annotations (not human acceptance)",
        "reference_sha256": sha256(reference), "notes_sha256": sha256(notes),
        "complete": True,
        "assessments": [
            {"concept_id": "unit-distinction", "verdict": "distorted",
             "quote": "The signal is .5 MV.", "reason": "Unit case changed."},
            {"concept_id": "area", "verdict": "covered", "quote": "The area is 2 cm².",
             "reason": "Area retained."},
            {"concept_id": "worked-example", "verdict": "covered", "quote": "x = −2",
             "reason": "Example retained."},
            {"concept_id": "qualification", "verdict": "missing", "quote": "",
             "reason": "Positive-input qualification absent."},
        ],
        "unsupported_additions": [{"quote": "The experiment was performed in 2024.",
                                   "reason": "Date absent from reference."}],
    }


def test_known_edit_distances_and_empty_candidate():
    assert word_errors("a b c", "a z c")["edit_distance"] == 1
    assert word_errors("a b", "a b c")["wer"] == .5
    assert word_errors("a b", "a")["wer"] == .5
    assert word_errors("a b", "")["wer"] == 1
    assert word_errors("a", "a b c")["wer"] == 2


def test_sensitive_notation_is_not_normalized():
    assert word_errors(".5 mV cm² x₁ −2", ".5 MV cm2 x1 -2")["edit_distance"] == 4
    assert word_errors("a   b\nc", "a b c")["wer"] == 0


def test_synthetic_regression_and_immutable_inputs():
    before = inputs()
    report = evaluate(*before)
    assert report["reference_status"] == "synthetic"
    assert report["transcription"]["edit_distance"] == 3
    assert report["transcription"]["reference_words"] == 29
    assert report["transcription"]["critical_checks_present"] == 2
    assert report["notes"]["status"] == "unchecked"
    assert report["notes"]["missing"] is None
    assert report["acceptance"] == "not_assessed"
    assert inputs() == before


def test_controlled_review_reports_omission_distortion_and_addition():
    reference, transcript, notes = inputs()
    report = evaluate(reference, transcript, notes,
                      json.dumps(review_for(reference, notes)).encode())
    assert report["notes"]["covered"] == 2
    assert report["notes"]["distorted"] == 1
    assert report["notes"]["missing"] == 1
    assert report["notes"]["unsupported_additions"] == 1
    assert report["acceptance"] == "not_assessed"


@pytest.mark.parametrize("fault", ["hash", "reference_hash", "duplicate", "unknown", "missing",
                                        "quote", "addition_quote", "partial", "reviewer"])
def test_invalid_or_stale_review_is_rejected(fault):
    reference, transcript, notes = inputs()
    review = review_for(reference, notes)
    if fault == "hash":
        review["notes_sha256"] = "0" * 64
    elif fault == "reference_hash":
        review["reference_sha256"] = "0" * 64
    elif fault == "duplicate":
        review["assessments"].append(review["assessments"][0])
    elif fault == "unknown":
        review["assessments"][0]["concept_id"] = "unknown"
    elif fault == "missing":
        review["assessments"].pop()
    elif fault == "quote":
        review["assessments"][0]["quote"] = "invented quote"
    elif fault == "addition_quote":
        review["unsupported_additions"][0]["quote"] = "invented quote"
    elif fault == "partial":
        review["complete"] = False
    else:
        review["reviewer"] = " "
    with pytest.raises(ValueError):
        evaluate(reference, transcript, notes, json.dumps(review).encode())


@pytest.mark.parametrize("fault", ["human", "permission", "duplicate", "phrase", "extra", "empty"])
def test_reference_validation(fault):
    reference, transcript, notes = inputs()
    ref = json.loads(reference)
    if fault == "human":
        ref["reference_status"] = "human_reviewed"
    elif fault == "permission":
        ref["permission_confirmed"] = False
    elif fault == "duplicate":
        ref["critical_checks"].append(ref["critical_checks"][0])
    elif fault == "phrase":
        ref["critical_checks"][0]["phrase"] = "absent phrase"
    elif fault == "extra":
        ref["unknown"] = True
    else:
        ref["transcript"] = " "
    with pytest.raises(ValueError):
        evaluate(json.dumps(ref).encode(), transcript, notes)


def test_alignment_work_is_bounded():
    with pytest.raises(ValueError, match="bounded excerpts"):
        word_errors("a " * 2001, "a " * 2000)
    with pytest.raises(ValueError, match="bounded excerpts"):
        word_errors("a", "a " * 4001)
    with pytest.raises(ValueError, match="contain words"):
        word_errors(" ", "a")


def test_cli_report_is_new_and_inputs_remain_unchanged(tmp_path):
    output = tmp_path / "report.json"
    args = ["--reference", str(FIXTURES / "reference.json"), "--transcript",
            str(FIXTURES / "transcript.txt"), "--notes", str(FIXTURES / "notes.txt"),
            "--output", str(output)]
    before = inputs()
    assert main(args) == 0
    saved = output.read_bytes()
    assert json.loads(saved)["notes"]["status"] == "unchecked"
    assert main(args) == 1
    assert output.read_bytes() == saved
    args[-1] = str(FIXTURES / "notes.txt")
    assert main(args) == 1
    assert inputs() == before


def test_cli_rejects_invalid_utf8_and_does_not_write_report(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff")
    report = tmp_path / "report.json"
    assert main(["--reference", str(FIXTURES / "reference.json"), "--transcript", str(bad),
                 "--notes", str(FIXTURES / "notes.txt"), "--output", str(report)]) == 1
    assert not report.exists()


def test_main_cli_routes_benchmark(tmp_path):
    from videomind.cli import main as cli_main
    assert cli_main(["benchmark", "--reference", str(FIXTURES / "reference.json"),
                     "--transcript", str(FIXTURES / "transcript.txt"), "--notes",
                     str(FIXTURES / "notes.txt"), "--output", str(tmp_path / "report.json")]) == 0
