"""Repeatable offline content gates; never a production certification."""
from pathlib import Path

from pydantic import Field, model_validator

from .benchmark_service import Contract, evaluate, sha256


class QualityPolicy(Contract):
    max_wer: float = Field(ge=0, allow_inf_nan=False)
    min_critical_recall: float = Field(ge=0, le=1, allow_inf_nan=False)
    max_missing: int = Field(ge=0)
    max_distorted: int = Field(ge=0)
    max_unsupported_additions: int = Field(ge=0)
    min_reviewed_sources: int = Field(ge=1)
    required_slices: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_slices(self):
        if any(not tag.strip() for tag in self.required_slices):
            raise ValueError("Slice labels must contain text")
        if len(set(self.required_slices)) != len(self.required_slices):
            raise ValueError("Duplicate required slices")
        return self


class EvaluationSample(Contract):
    reference: str = Field(min_length=1)
    transcript: str = Field(min_length=1)
    notes: str = Field(min_length=1)
    review: str | None = None
    slices: list[str] = Field(min_length=1, max_length=100)


class EvaluationSuite(Contract):
    schema_version: int = Field(ge=1, le=1)
    suite_id: str = Field(min_length=1)
    policy: QualityPolicy
    samples: list[EvaluationSample] = Field(min_length=1, max_length=100)


def evaluate_suite(manifest_bytes: bytes, base_dir: Path) -> dict:
    """Recompute from artifacts, binding reviews to bytes through evaluate().

    Paths are local, resolved relative to the manifest. No inference or fetching.
    Each metric is gated per sample so strong examples cannot hide bad ones.
    """
    suite = EvaluationSuite.model_validate_json(manifest_bytes)
    results, seen_ids, seen_refs = [], set(), set()
    reviewed_sources, reviewed_slices = set(), set()
    incomplete, failures = [], []
    for sample in suite.samples:
        def read(name):
            return (base_dir / name).read_bytes()

        result = evaluate(read(sample.reference), read(sample.transcript), read(sample.notes),
                          read(sample.review) if sample.review is not None else None)
        sample_id = result["sample_id"]
        reference_hash = result["hashes"]["reference_sha256"]
        if sample_id in seen_ids or reference_hash in seen_refs:
            raise ValueError("Duplicate sample ID or reference in evaluation suite")
        seen_ids.add(sample_id)
        seen_refs.add(reference_hash)
        transcription, notes = result["transcription"], result["notes"]
        recall = transcription["critical_checks_present"] / len(transcription["critical_checks"])
        failed, missing = [], []
        if transcription["wer"] > suite.policy.max_wer:
            failed.append("wer")
        if recall < suite.policy.min_critical_recall:
            failed.append("critical_phrase_recall")
        if result["reference_status"] != "human_reviewed":
            missing.append("human_reference")
        if notes["status"] != "human_reviewed":
            missing.append("human_notes_review")
        else:
            for metric in ("missing", "distorted", "unsupported_additions"):
                if notes[metric] > getattr(suite.policy, f"max_{metric}"):
                    failed.append(metric)
        if not missing:
            reviewed_sources.add(result["source_sha256"])
            reviewed_slices.update(sample.slices)
        failures.extend(f"{sample_id}: {item}" for item in failed)
        incomplete.extend(f"{sample_id}: {item}" for item in missing)
        results.append({"sample_id": sample_id, "slices": sample.slices,
                        "status": "failed" if failed else "incomplete" if missing else "passed",
                        "failed_metrics": failed, "missing_evidence": missing,
                        "critical_phrase_recall": recall, "benchmark": result})
    if len(reviewed_sources) < suite.policy.min_reviewed_sources:
        incomplete.append("insufficient_distinct_reviewed_sources")
    missing_slices = sorted(set(suite.policy.required_slices) - reviewed_slices)
    if missing_slices:
        incomplete.append("missing_reviewed_slices")
    return {"schema_version": 1, "evaluator_version": "1", "suite_id": suite.suite_id,
            "manifest_sha256": sha256(manifest_bytes), "policy": suite.policy.model_dump(),
            "content_gate": "failed" if failures else "incomplete" if incomplete else "passed",
            "production_readiness": "not_assessed", "failed_checks": failures,
            "missing_evidence": incomplete, "missing_slices": missing_slices,
            "distinct_reviewed_sources": len(reviewed_sources), "samples": results,
            "limitations": ["Policy thresholds are supplied by the suite author, not validated standards.",
                            "Reviewers, source hashes and slice labels are declarations, not authenticated.",
                            "Literal phrase recall is not semantic recall or factual verification.",
                            "This suite does not measure reliability, security, load or external factual accuracy."]}


def input_paths(manifest_bytes: bytes, base_dir: Path) -> set[Path]:
    suite = EvaluationSuite.model_validate_json(manifest_bytes)
    return {(base_dir / name).resolve() for sample in suite.samples
            for name in (sample.reference, sample.transcript, sample.notes, sample.review)
            if name is not None}
