"""Withhold problematic generated content; retain the original candidate and audit."""
from copy import deepcopy
import re
from typing import Literal
from pydantic import create_model
from .knowledge_models import EditorialAssessment

BLOCKING = {"claim_unsupported", "claim_uncertain", "factual_risk", "numeric_mismatch",
            "unit_or_notation_mismatch", "unreliable_concept", "excessive_similarity", "nontechnical_chatter"}
METADATA = re.compile(r"\b(?:concept\s+C\d{4,6}|verification status(?:es)?|provided passages|"
                      r"transcription uncertainty|according to E\d{4,6})\b", re.I)
INTERNAL_CITATION = re.compile(r"\s*\(C\d{4,6}(?:\s*,\s*C\d{4,6})*\)")


def make_reading_copy(session, document, knowledge, quality):
    concepts = {item["id"]: item for item in knowledge["concepts"]}
    assessments = {item["item_id"]: item for item in quality["assessments"]}
    factual = {item["item_id"]: item for item in quality["factual_risk_assessments"]}
    result = deepcopy(document)
    result["sections"] = []
    audit = {"policy": "withhold_flagged_content_v1", "retained": [], "withheld": [], "edits": [],
             "complete_lecture_coverage": False, "externally_fact_checked": False}
    for section in document["sections"]:
        kept = []
        for paragraph in section["paragraphs"]:
            item_id = paragraph["id"]
            dependencies = {item_id, *paragraph["concept_ids"]}
            reasons = [{"code": issue["code"], "item_id": issue["item_id"], "detail": issue["detail"]}
                       for issue in quality["issues"] if issue["item_id"] in dependencies and issue["code"] in BLOCKING]
            if any(assessments.get(key, {}).get("verdict") != "supported" for key in dependencies):
                reasons.append({"code": "support_not_established", "detail": "Every paragraph and concept must have a supported assessment."})
            if any(factual.get(key, {}).get("risk") != "no_obvious_issue" for key in paragraph["concept_ids"]):
                reasons.append({"code": "factual_risk_not_cleared", "detail": "Concept plausibility review is missing or requires review."})
            source_quotes = [citation["quote"] for key in paragraph["concept_ids"] for citation in concepts[key]["citations"]]
            if METADATA.search(paragraph["text"]) and not any(METADATA.search(text) for text in source_quotes):
                reasons.append({"code": "editorial_metadata_leak", "detail": "The generated explanation discusses pipeline metadata as lesson content."})
            edited = deepcopy(paragraph)
            # Remove generated citation markers only; preserve literal identifiers found in source.
            edited["text"] = INTERNAL_CITATION.sub(lambda match: match.group() if any(
                match.group().strip() in quote for quote in source_quotes) else "", paragraph["text"])
            if not reasons:
                schema = create_model("EditorialAssessment", __base__=EditorialAssessment,
                                      item_id=(Literal[item_id], ...))
                editorial = session.ask("editorial", """Decide whether this paragraph supplies substantive technical
education relevant to the document's MAIN technical subject, rather than classroom conversation, introductions, attendance/session logistics, jokes,
family discussion, sales pitches, job guarantees, vague filler, or commentary about verification.
The supplied section heading is generated and is not evidence of relevance. Formal wording alone
does not make a paragraph technical. Exclude vague filler that teaches no mechanism, rule or example.
For example, banter about participants' children in a programming lesson is not programming knowledge;
an evidence-based child-development explanation in a child-development lesson may be relevant.
Judge meaning and context, not keywords alone. Preserve genuine technical examples, caveats and
code strings even if they contain greetings. Use uncertain for ambiguous/garbled wording.
Return technical only for meaningful technical content. Do not correct or invent facts.""",
                    {"item_id": item_id, "document_topic": document["title"], "heading": section["heading"], "paragraph": edited["text"],
                     "source_quotes": source_quotes}, schema)
                if editorial.item_id != item_id:
                    raise ValueError("Editorial review assessed an unexpected paragraph")
                if editorial.decision != "technical":
                    reasons.append({"code": "editorial_" + editorial.decision, "detail": editorial.reason})
            if reasons:
                audit["withheld"].append({"item_id": item_id, "heading": section["heading"],
                    "paragraph": deepcopy(paragraph), "reasons": reasons})
            else:
                kept.append(edited)
                audit["retained"].append(item_id)
                if edited["text"] != paragraph["text"]:
                    audit["edits"].append({"item_id": item_id, "reason": "removed_generated_citation_markers",
                                          "original": paragraph["text"], "reading_text": edited["text"]})
        if kept:
            result["sections"].append({"heading": section["heading"], "paragraphs": kept})
    audit["counts"] = {"retained": len(audit["retained"]), "withheld": len(audit["withheld"])}
    audit["state"] = "partial_reading_copy" if audit["retained"] else "no_content_passed"
    result["content_gate"] = {key: audit[key] for key in ("policy", "counts", "state", "complete_lecture_coverage")}
    return result, audit
