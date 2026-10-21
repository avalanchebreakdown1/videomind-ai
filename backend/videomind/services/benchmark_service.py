"""Offline sample evaluation. Literal checks and WER are not factual verification."""
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CriticalCheck(Contract):
    id: str = Field(min_length=1)
    category: Literal["term", "number", "negation", "example", "boundary"]
    phrase: str = Field(min_length=1)


class Concept(Contract):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class Reference(Contract):
    schema_version: Literal[1]
    sample_id: str = Field(min_length=1)
    reference_status: Literal["synthetic", "human_reviewed"]
    source_description: str = Field(min_length=1)
    permission_confirmed: bool
    reviewed_by: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    transcript: str = Field(min_length=1, max_length=100_000)
    critical_checks: list[CriticalCheck] = Field(min_length=1, max_length=100)
    concepts: list[Concept] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_reference(self):
        if not self.transcript.strip():
            raise ValueError("Reference transcript must contain words")
        if not self.permission_confirmed:
            raise ValueError("Source permission must be confirmed")
        if self.reference_status == "human_reviewed" and (
            not self.reviewed_by or not self.reviewed_by.strip() or not self.source_sha256
        ):
            raise ValueError("Human reference requires reviewer and source SHA-256")
        for items in (self.critical_checks, self.concepts):
            if len({item.id for item in items}) != len(items):
                raise ValueError("Duplicate reference IDs")
        for check in self.critical_checks:
            if not check.phrase.strip() or check.phrase not in self.transcript:
                raise ValueError("Critical phrases must occur verbatim in reference")
        return self


class ConceptAssessment(Contract):
    concept_id: str
    verdict: Literal["covered", "distorted", "missing"]
    quote: str
    reason: str = Field(min_length=1)


class UnsupportedAddition(Contract):
    quote: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class NotesReview(Contract):
    reviewer: str = Field(min_length=1)
    reference_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    notes_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    complete: bool
    assessments: list[ConceptAssessment] = Field(max_length=100)
    unsupported_additions: list[UnsupportedAddition] = Field(max_length=100)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word_errors(reference: str, candidate: str) -> dict:
    """Case/punctuation-sensitive whitespace tokens; rolling-row Levenshtein distance."""
    expected, actual = reference.split(), candidate.split()
    if not expected:
        raise ValueError("Reference transcript must contain words")
    if max(len(expected), len(actual)) > 4000 or len(expected) * len(actual) > 4_000_000:
        raise ValueError("Sample too long: use bounded excerpts (4000 tokens, 4M alignment cells)")
    row = list(range(len(actual) + 1))
    for i, token in enumerate(expected, 1):
        next_row = [i]
        for j, other in enumerate(actual, 1):
            next_row.append(min(row[j] + 1, next_row[j - 1] + 1,
                                row[j - 1] + (token != other)))
        row = next_row
    return {"reference_words": len(expected), "candidate_words": len(actual),
            "edit_distance": row[-1], "wer": row[-1] / len(expected)}


def evaluate(reference_bytes: bytes, transcript_bytes: bytes, notes_bytes: bytes,
             review_bytes: bytes | None = None) -> dict:
    reference = Reference.model_validate_json(reference_bytes)
    transcript, notes = transcript_bytes.decode("utf-8"), notes_bytes.decode("utf-8")
    hashes = {"reference_sha256": sha256(reference_bytes),
              "transcript_sha256": sha256(transcript_bytes), "notes_sha256": sha256(notes_bytes)}
    checks = [{"id": check.id, "category": check.category, "phrase": check.phrase,
               "present": check.phrase in transcript} for check in reference.critical_checks]
    notes_result = {"status": "unchecked", "covered": None, "distorted": None,
                    "missing": None, "unsupported_additions": None}
    if review_bytes is not None:
        review = NotesReview.model_validate_json(review_bytes)
        if not review.reviewer.strip() or not review.complete:
            raise ValueError("Notes review must be complete and name a reviewer")
        if review.reference_sha256 != hashes["reference_sha256"] or review.notes_sha256 != hashes["notes_sha256"]:
            raise ValueError("Notes review hashes do not match evaluated files")
        ids = [item.concept_id for item in review.assessments]
        if len(set(ids)) != len(ids) or set(ids) != {item.id for item in reference.concepts}:
            raise ValueError("Notes review must assess each concept exactly once")
        for item in review.assessments:
            if item.verdict == "missing":
                if item.quote:
                    raise ValueError("Missing concepts must have an empty quote")
            elif not item.quote.strip() or item.quote not in notes:
                raise ValueError("Review quotes must occur verbatim in notes")
        for item in review.unsupported_additions:
            if not item.quote.strip() or item.quote not in notes:
                raise ValueError("Unsupported-addition quotes must occur verbatim in notes")
        notes_result = {"status": "human_reviewed", "reviewer": review.reviewer,
                        **{v: sum(item.verdict == v for item in review.assessments)
                           for v in ("covered", "distorted", "missing")},
                        "unsupported_additions": len(review.unsupported_additions),
                        "review": review.model_dump(), "review_sha256": sha256(review_bytes)}
    return {"schema_version": 1, "evaluator_version": "1",
            "sample_id": reference.sample_id, "reference_status": reference.reference_status,
            "source_description": reference.source_description,
            "reference_reviewer": reference.reviewed_by, "source_sha256": reference.source_sha256,
            "hashes": hashes,
            "transcription": {**word_errors(reference.transcript, transcript),
                              "normalization": "whitespace tokens; case and Unicode punctuation preserved",
                              "critical_checks": checks,
                              "critical_checks_present": sum(item["present"] for item in checks)},
            "notes": notes_result, "acceptance": "not_assessed",
            "limitations": ["Literal presence does not establish correct meaning or alignment.",
                            "Notes findings are supplied by a reviewer, not inferred by this evaluator.",
                            "No external factual verification or lecture-wide accuracy acceptance."]}
