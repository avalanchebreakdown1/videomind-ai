"""Validate saved extraction against current source and original model evidence."""
import json
from pathlib import Path
from .knowledge_models import SelectedConcept
from .verification_service import sha256


def load_reusable_knowledge(directory, hashes, prepared, evidence, batches, settings):
    directory = Path(directory).resolve()
    paths = []

    def read(name):
        path = directory / name
        if not path.is_file() or path.stat().st_size > 20_000_000:
            raise ValueError("Missing or oversized reusable extraction artifact")
        paths.append(path)
        return json.loads(path.read_text())

    manifest = read("manifest.json")
    if manifest.get("kind") != "educational_document" or manifest.get("source_artifacts_sha256") != hashes:
        raise ValueError("Reusable extraction source hashes do not match current source")
    if read("prepared_source.json") != prepared or read("evidence.json")["passages"] != evidence:
        raise ValueError("Reusable extraction evidence does not match current source")
    knowledge = read("knowledge.json")
    if knowledge.get("citation_method") != "application_copied_passage_v1":
        raise ValueError("Reuse requires application-copied evidence references")
    attempts = read("extraction_validation.json")["attempts"]
    successful = [item for item in attempts if item["valid"]]
    if [item["batch"] for item in successful] != list(range(1, len(batches) + 1)):
        raise ValueError("Reusable extraction does not cover every source batch exactly once")
    canonical, unrepresented = [], []
    for saved, batch in zip(successful, batches):
        stage = "extract" if saved["attempt"] == 1 else "extract-retry"
        prefix = f"model_calls/{saved['model_call']:04d}-{stage}"
        request, response = read(prefix + ".request.json"), read(prefix + ".response.json")
        data = json.loads(request["messages"][1]["content"].split("\nUNTRUSTED_DATA_JSON:\n", 1)[1])
        if data != batch or request["format"].get("title") != "EvidenceSelection":
            raise ValueError("Reusable extraction request does not match source batch")
        if response.get("done") is not True or response.get("done_reason") == "length":
            raise ValueError("Reusable extraction response was incomplete")
        selected = json.loads(response["message"]["content"])
        if set(selected) != {"concepts"} or not isinstance(selected["concepts"], list) or len(selected["concepts"]) > 10:
            raise ValueError("Invalid reusable extraction response")
        allowed, used = {item["id"]: item["text"] for item in batch}, set()
        for value in selected["concepts"]:
            item = SelectedConcept.model_validate(value)
            copied = item.model_dump()
            citations = []
            for reference in item.citations:
                if reference.evidence_id not in allowed:
                    raise ValueError("Reusable extraction contains an unknown evidence ID")
                used.add(reference.evidence_id)
                citations.append({"evidence_id": reference.evidence_id, "quote": allowed[reference.evidence_id]})
            copied["citations"] = citations
            canonical.append({"id": f"C{len(canonical) + 1:04d}", **copied})
        unrepresented.extend(item["id"] for item in batch if item["id"] not in used)
    if not canonical or knowledge["concepts"] != canonical or knowledge["unrepresented_evidence_ids"] != unrepresented:
        raise ValueError("Saved knowledge does not match original extraction responses and source quotations")
    if len(canonical) > settings.max_concepts:
        raise ValueError("Reusable knowledge exceeds configured concept limit")
    audit = {"directory": str(directory), "artifacts_sha256": {str(p.relative_to(directory)): sha256(p) for p in paths},
             "validation": "reconstructed_from_original_model_responses_and_current_source"}
    return knowledge, audit
