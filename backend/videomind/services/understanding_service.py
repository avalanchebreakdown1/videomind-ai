"""Extract evidence-linked concepts, not rewritten transcript sentences."""
from typing import Literal
from pydantic import create_model, Field, ValidationError
from .knowledge_models import Extraction, EvidenceReference, SelectedConcept, StrictModel
from .document_service import write_json


EXTRACTION_INSTRUCTION = """Extract important technical concepts from these evidence passages.
Group related details into concepts. Return prerequisites (topic names), explanations and caveats.
Every concept needs citations containing ONLY evidence_id values selected from these passages.
Do not output quotes: the application copies the original evidence text directly from the selected IDs.
Select only passages that support the explanation; an existing ID alone does not establish support.
Do not resolve disputed/uncertain wording. Do not extract session-start/attendance logistics,
participant family discussions, jokes, sales pitches, job guarantees or claims about guaranteed ease.
Keep technical examples and qualifications. Do not turn garbled words into invented concepts.
Return [] if nothing substantive and technical is supported; there is no minimum concept quota.
Explanations must follow the source, including assumptions and limits. Do not introduce outside facts."""


def extract_batch(session, batch, batch_index, validation, concept_limit=10):
    """Select constrained IDs; source quotations are copied by application code."""
    allowed = {entry["id"]: entry for entry in batch}
    reference = create_model("BatchReference", __base__=EvidenceReference,
                             evidence_id=(Literal[tuple(allowed)], ...))
    concept = create_model("BatchSelectedConcept", __base__=SelectedConcept,
                           citations=(list[reference], Field(min_length=1, max_length=5)))
    schema = create_model("EvidenceSelection", __base__=StrictModel,
                          concepts=(list[concept], Field(max_length=concept_limit)))
    instruction = EXTRACTION_INSTRUCTION + f"\nReturn at most {concept_limit} concepts; synthesize related details."
    for attempt in range(2):
        problems = []
        try:
            result = session.ask("extract" if attempt == 0 else "extract-retry", instruction, batch, schema)
        except ValidationError:
            problems.append({"reason": "invalid_reference_selection_schema"})
        validation.append({"batch": batch_index, "attempt": attempt + 1, "model_call": session.calls,
                           "valid": not problems, "problems": problems})
        write_json(session.directory.parent / "extraction_validation.json", {"attempts": validation})
        if not problems:
            canonical = []
            for item in result.concepts:
                value = item.model_dump()
                value["citations"] = [{"evidence_id": citation.evidence_id,
                                       "quote": allowed[citation.evidence_id]["text"]}
                                      for citation in item.citations]
                canonical.append(value)
            assembled = Extraction.model_validate({"concepts": canonical})
            for item in assembled.concepts:
                for citation in item.citations:
                    # Preserve even source whitespace; the generic text schema strips it.
                    citation.quote = allowed[citation.evidence_id]["text"]
            return assembled
        if attempt == 0:
            instruction += ("\nThe previous selection did not match the schema. Use only the supplied evidence IDs "
                            "and allowed fields; do not include a quote field or exceed the concept limit.")
    raise ValueError(f"Extraction invented an evidence ID or returned invalid reference fields in batch {batch_index}; "
                     "the single bounded retry also failed. See extraction_validation.json and model_calls.")


def build_evidence(source, chunk_chars):
    evidence, batches, current, size = [], [], [], 0
    for segment in source["retained_segments"]:
        text = segment["text"]
        # Split very long sentences at whitespace; never change mathematical tokens.
        start = 0
        while start < len(text):
            end = min(len(text), start + min(1200, chunk_chars))
            if end < len(text):
                split = text.rfind(" ", start, end)
                if split <= start:
                    raise ValueError("Source contains an oversized unbroken token")
                end = split
            part = text[start:end]
            if part.strip():
                entry = {"id": f"E{len(evidence) + 1:04d}", "text": part,
                         "source_char_start": segment["source_char_start"] + start,
                         "source_char_end": segment["source_char_start"] + end,
                         "start": segment["start"], "end": segment["end"],
                         "verification_statuses": segment["verification_statuses"]}
                evidence.append(entry)
                cost = len(part) + 250
                if current and size + cost > chunk_chars:
                    batches.append(current)
                    current, size = [], 0
                current.append(entry)
                size += cost
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
    if current:
        batches.append(current)
    return evidence, batches


def extract_knowledge(session, batches, max_concepts, on_batch=lambda done, total: None):
    concepts, unrepresented, validation = [], [], []
    if len(batches) > max_concepts:
        raise ValueError("Concept budget cannot represent every extraction batch")
    # Reserve model calls for writing and two separate concept reviews. This is
    # a disclosed extraction granularity, not truncation of source batches.
    count = max(1, len(batches))
    review_budget = max(1, (session.settings.max_calls - count - 1) // (5 * count))
    per_batch = min(10, max_concepts // count, review_budget)
    for batch_index, batch in enumerate(batches, 1):
        result = extract_batch(session, batch, batch_index, validation, per_batch)
        for item in result.concepts:
            concepts.append({"id": f"C{len(concepts) + 1:04d}", **item.model_dump()})
            if len(concepts) > max_concepts:
                raise ValueError("Concept limit exceeded; use a smaller source or a larger configured limit")
        used = {c.evidence_id for item in result.concepts for c in item.citations}
        unrepresented.extend(entry["id"] for entry in batch if entry["id"] not in used)
        on_batch(batch_index, len(batches))
    if not concepts:
        raise ValueError("No supported technical concepts were extracted")
    return {"kind": "evidence_linked_knowledge", "concepts": concepts,
            "citation_method": "application_copied_passage_v1", "concept_budget_per_batch": per_batch,
            "unrepresented_evidence_ids": unrepresented, "externally_fact_checked": False}
