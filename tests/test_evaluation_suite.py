import json
from pathlib import Path

import pytest

from videomind.cli import main
from videomind.services.benchmark_service import sha256
from videomind.services.evaluation_suite_service import evaluate_suite


FIXTURES = Path(__file__).parent / "fixtures" / "benchmark"


def make_suite(tmp_path, *, human=True, review=True):
    reference = {
        "schema_version": 1, "sample_id": "reviewed-sample",
        "reference_status": "human_reviewed" if human else "synthetic",
        "source_description": "Controlled test declarations, not actual educator approval",
        "permission_confirmed": True, "reviewed_by": "Test reviewer",
        "source_sha256": "a" * 64, "transcript": "Keep .5 mW.",
        "critical_checks": [{"id": "unit", "category": "number", "phrase": ".5 mW"}],
        "concepts": [{"id": "power", "description": "Power with exact unit"}],
    }
    ref_bytes = json.dumps(reference).encode()
    notes = b"Keep .5 mW."
    (tmp_path / "ref.json").write_bytes(ref_bytes)
    (tmp_path / "transcript.txt").write_bytes(notes)
    (tmp_path / "notes.txt").write_bytes(notes)
    annotations = {
        "reviewer": "Test reviewer", "reference_sha256": sha256(ref_bytes),
        "notes_sha256": sha256(notes), "complete": True,
        "assessments": [{"concept_id": "power", "verdict": "covered",
                         "quote": notes.decode(), "reason": "Exact unit retained"}],
        "unsupported_additions": [],
    }
    (tmp_path / "review.json").write_text(json.dumps(annotations))
    suite = json.loads((FIXTURES / "suite.json").read_bytes())
    suite["policy"].update(min_reviewed_sources=1, required_slices=["technical"])
    suite["samples"] = [{"reference": "ref.json", "transcript": "transcript.txt",
                         "notes": "notes.txt", "review": "review.json" if review else None,
                         "slices": ["technical"]}]
    return suite


def run(suite, tmp_path):
    return evaluate_suite(json.dumps(suite).encode(), tmp_path)


def test_synthetic_baseline_fails_without_making_production_claim():
    report = evaluate_suite((FIXTURES / "suite.json").read_bytes(), FIXTURES)
    assert report["content_gate"] == "failed"
    assert report["failed_checks"] == ["synthetic-technical-001: wer",
                                        "synthetic-technical-001: critical_phrase_recall"]
    assert report["distinct_reviewed_sources"] == 0
    assert report["production_readiness"] == "not_assessed"


def test_reviewed_pass_is_scoped_and_preserves_artifacts(tmp_path):
    suite = make_suite(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    report = run(suite, tmp_path)
    assert report["content_gate"] == "passed"
    assert report["production_readiness"] == "not_assessed"
    assert report["manifest_sha256"] == sha256(json.dumps(suite).encode())
    assert all(p.read_bytes() == content for p, content in before.items())


@pytest.mark.parametrize("human,review", [(False, True), (True, False), (False, False)])
def test_perfect_text_cannot_pass_without_real_reference_and_review(tmp_path, human, review):
    report = run(make_suite(tmp_path, human=human, review=review), tmp_path)
    assert report["content_gate"] == "incomplete"
    assert report["distinct_reviewed_sources"] == 0
    assert report["missing_slices"] == ["technical"]


def test_coverage_counts_distinct_sources_and_requires_each_slice(tmp_path):
    suite = make_suite(tmp_path)
    suite["policy"].update(min_reviewed_sources=2, required_slices=["technical", "noisy"])
    report = run(suite, tmp_path)
    assert report["content_gate"] == "incomplete"
    assert report["missing_slices"] == ["noisy"]
    # A second excerpt from the same recording must not count as a second source.
    ref = json.loads((tmp_path / "ref.json").read_bytes())
    ref["sample_id"] = "second-excerpt"
    ref_bytes = json.dumps(ref).encode()
    (tmp_path / "ref2.json").write_bytes(ref_bytes)
    review = json.loads((tmp_path / "review.json").read_bytes())
    review["reference_sha256"] = sha256(ref_bytes)
    (tmp_path / "review2.json").write_text(json.dumps(review))
    suite["samples"].append({**suite["samples"][0], "reference": "ref2.json",
                              "review": "review2.json", "slices": ["noisy"]})
    report = run(suite, tmp_path)
    assert report["distinct_reviewed_sources"] == 1
    assert report["missing_slices"] == []
    assert report["content_gate"] == "incomplete"


def test_one_bad_sample_cannot_be_hidden_by_average(tmp_path):
    suite = make_suite(tmp_path)
    (tmp_path / "transcript.txt").write_text("Keep .5 MW.")
    report = run(suite, tmp_path)
    assert report["content_gate"] == "failed"
    assert "reviewed-sample: critical_phrase_recall" in report["failed_checks"]


@pytest.mark.parametrize("metric", ["missing", "distorted", "unsupported_additions"])
def test_reviewed_content_errors_fail(tmp_path, metric):
    suite = make_suite(tmp_path)
    review = json.loads((tmp_path / "review.json").read_bytes())
    if metric == "unsupported_additions":
        review[metric] = [{"quote": "Keep .5 mW.", "reason": "Controlled finding"}]
    else:
        review["assessments"][0].update(verdict=metric, quote="" if metric == "missing" else "Keep .5 mW.")
    (tmp_path / "review.json").write_text(json.dumps(review))
    report = run(suite, tmp_path)
    assert report["content_gate"] == "failed"
    assert f"reviewed-sample: {metric}" in report["failed_checks"]


def test_duplicate_reference_and_stale_reviews_are_rejected(tmp_path):
    suite = make_suite(tmp_path)
    suite["samples"].append(suite["samples"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        run(suite, tmp_path)
    suite["samples"].pop()
    (tmp_path / "notes.txt").write_text("Changed notes")
    with pytest.raises(ValueError, match="hashes"):
        run(suite, tmp_path)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_thresholds_cannot_bypass_gate(tmp_path, value):
    suite = make_suite(tmp_path)
    suite["policy"]["max_wer"] = value
    with pytest.raises(ValueError):
        run(suite, tmp_path)


def test_cli_exit_codes_and_overwrite_protection(tmp_path):
    suite = make_suite(tmp_path)
    manifest = tmp_path / "suite.json"
    manifest.write_text(json.dumps(suite))
    output = tmp_path / "report.json"
    args = ["evaluate", "--suite", str(manifest), "--output", str(output)]
    assert main(args) == 0
    saved = output.read_bytes()
    assert main(args) == 1
    assert output.read_bytes() == saved
    assert main(args[:-1] + [str(tmp_path / "notes.txt")]) == 1
    (tmp_path / "transcript.txt").write_text("wrong")
    assert main(args[:-1] + [str(tmp_path / "failed.json")]) == 2
    (tmp_path / "notes.txt").write_text("stale review")
    assert main(args[:-1] + [str(tmp_path / "invalid.json")]) == 1
    assert not (tmp_path / "invalid.json").exists()
