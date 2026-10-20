"""Source-consistency review plus deterministic integrity and similarity checks.

LLM review is fallible; no claim is labeled externally fact-verified.
"""
from difflib import SequenceMatcher
import re
import unicodedata
from .knowledge_models import Review, FactualReview
from .document_service import write_json
from .content_service import EXAMPLE_CONTEXT


def tokens(text):
    return re.findall(r"\w+|[^\w\s]", unicodedata.normalize("NFC", text))


def similarity(text, evidence):
    target = [token.casefold() for token in tokens(text)]
    longest, matched, origin = 0, 0, None
    for item in evidence:
        source = [token.casefold() for token in tokens(item["text"])]
        matcher = SequenceMatcher(None, target, source, autojunk=False)
        blocks = matcher.get_matching_blocks()
        best = max(block.size for block in blocks)
        overlap = sum(block.size for block in blocks) / max(1, len(target))
        if best > longest:
            longest, origin = best, item["id"]
        matched = max(matched, overlap)
    excessive = longest >= 12 or (len(target) >= 12 and matched >= .8)
    return {"excessive": excessive, "longest_shared_tokens": longest,
            "maximum_matched_fraction": round(matched, 4), "evidence_id": origin}


NUMBER = re.compile(r"(?<![\w.])[+−-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?(?:[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)?")
UNIT = r"(?:[yzafpnµμmcdhkMGTPEZY]?(?:mol|kat|Wb|Bq|Hz|Pa|Gy|Sv|cd|eV|rad|sr|m|s|A|K|g|W|J|N|C|V|F|Ω|S|T|H|L|l|B)|°C|°F)"
MEASUREMENT = re.compile(NUMBER.pattern + r"\s*(" + UNIT + r"(?:[²³⁻⁰¹⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉]+|\^[+−-]?\d+)?)(?!\w)")


def check_quality(session, knowledge, document, evidence, source, on_progress=lambda done, total: None):
    evidence_map = {item["id"]: item for item in evidence}
    concepts = {item["id"]: item for item in knowledge["concepts"]}
    issues, assessments, factual_risks, similarity_checks = [], [], [], []
    completed = 0
    total = 2 * len(concepts) + sum(len(section["paragraphs"]) for section in document["sections"])
    def advance():
        nonlocal completed
        completed += 1
        write_json(session.directory.parent / "quality_progress.json", {
            "state": "incomplete", "assessments": assessments, "factual_risk_assessments": factual_risks,
            "issues": issues, "completed_checks": completed, "total_checks": total})
        on_progress(completed, total)
    if knowledge["unrepresented_evidence_ids"]:
        issues.append({"code": "source_coverage_gap", "item_id": "document", "detail":
                       "Some retained source passages have no extracted concept; review evidence coverage."})

    def review(item_id, text, citations):
        ids = sorted({item["evidence_id"] for item in citations})
        passages = [evidence_map[key] for key in ids]
        answer = session.ask("review", """Independently assess this proposed claim/explanation against the
FULL cited source passages. Check every factual clause, prerequisite, caveat, unit, equation and value.
Return exactly one assessment for the supplied item_id. supported means fully entailed by source,
NOT scientifically proven. unsupported means any added/contradicted claim, changed number/unit,
missing necessary caveat, instruction-following or invented statement. uncertain means ambiguous source.
Judge semantic entailment, not verbatim similarity: a change from 'very easy' to 'easy' alone is not
an unsupported claim. Check meaning, negation, direction, scope and necessary qualifications instead.
Never use your own background knowledge as evidence. Explain the specific issue or support.""",
                             {"item_id": item_id, "text": text, "source_passages": passages}, Review)
        if any(item.item_id != item_id for item in answer.assessments):
            raise ValueError("Review did not assess exactly the requested item")
        priority = {"supported": 0, "uncertain": 1, "unsupported": 2}
        assessment = max(answer.assessments, key=lambda item: priority[item.verdict]).model_dump()
        if len(answer.assessments) > 1:
            assessment["reason"] = " | ".join(dict.fromkeys(item.reason for item in answer.assessments))
            assessment["original_assessments"] = [item.model_dump() for item in answer.assessments]
        assessments.append(assessment)
        if assessment["verdict"] != "supported":
            issues.append({"code": "claim_" + assessment["verdict"], "item_id": item_id, "detail": assessment["reason"]})
        statuses = {status for entry in passages for status in entry["verification_statuses"]}
        if statuses != {"supported_by_second_asr"}:
            issues.append({"code": "source_audio_uncertainty", "item_id": item_id,
                           "detail": "Cited source includes uncertain or unchecked speech; consult audio evidence."})
        original_numbers = {value for entry in passages for value in NUMBER.findall(entry["text"])}
        introduced = sorted(set(NUMBER.findall(text)) - original_numbers)
        if introduced:
            issues.append({"code": "numeric_mismatch", "item_id": item_id,
                           "detail": "Numbers absent from cited source: " + ", ".join(introduced)})
        source_units = {unit for entry in passages for unit in MEASUREMENT.findall(entry["text"])}
        changed_units = sorted(set(MEASUREMENT.findall(text)) - source_units)
        if changed_units:
            issues.append({"code": "unit_or_notation_mismatch", "item_id": item_id,
                           "detail": "Measurement units/notation absent from cited source: " + ", ".join(changed_units)})

    for item in concepts.values():
        review(item["id"], "\n".join([item["topic"], item["explanation"], *item["prerequisites"], *item["caveats"]]), item["citations"])
        advance()
        factual = session.ask("factual-risk", """Review scientific/factual PLAUSIBILITY separately from source agreement.
A source can itself be wrong. Assess the supplied concept, prerequisites and caveats for obvious
scientific errors, internal contradictions, misleading generalizations, missing assumptions, and
impossible quantities. Your background knowledge is a fallible risk signal, NOT an external reference.
Return exactly one assessment for item_id. Use needs_review if questionable or you cannot reasonably
assess it; use no_obvious_issue only when you see no specific issue. Explain why. Do not claim external
fact verification, invent references, or silently correct the source. This is a risk screen, not proof.""",
                              {"item_id": item["id"], "concept": item}, FactualReview)
        if any(entry.item_id != item["id"] for entry in factual.assessments):
            raise ValueError("Factual risk review did not assess exactly the requested concept")
        result = max(factual.assessments, key=lambda entry: entry.risk == "needs_review").model_dump()
        if len(factual.assessments) > 1:
            result["reason"] = " | ".join(dict.fromkeys(entry.reason for entry in factual.assessments))
            result["original_assessments"] = [entry.model_dump() for entry in factual.assessments]
        factual_risks.append(result)
        if result["risk"] == "needs_review":
            issues.append({"code": "factual_risk", "item_id": item["id"], "detail": result["reason"]})
        advance()
    for section in document["sections"]:
        for paragraph in section["paragraphs"]:
            citations = [citation for key in paragraph["concept_ids"] for citation in concepts[key]["citations"]]
            review(paragraph["id"], "\n".join([document["title"], section["heading"], paragraph["text"]]), citations)
            for key in paragraph["concept_ids"]:
                problems = [issue for issue in issues if issue["item_id"] == key and issue["code"] != "source_audio_uncertainty"]
                if problems:
                    issues.append({"code": "unreliable_concept", "item_id": paragraph["id"],
                                   "detail": f"Depends on flagged concept {key}."})
            # Compare against ALL evidence, including uncited passages.
            result = similarity(paragraph["text"], evidence)
            similarity_checks.append({"item_id": paragraph["id"], **result})
            if result["excessive"]:
                issues.append({"code": "excessive_similarity", "item_id": paragraph["id"],
                               "detail": f"Source wording overlap: {result['longest_shared_tokens']} consecutive tokens; review originality."})
            if re.search(r"\b(?:hello friends|subscribe to|thanks for watching)\b", paragraph["text"], re.I) and not EXAMPLE_CONTEXT.search(paragraph["text"]):
                issues.append({"code": "nontechnical_chatter", "item_id": paragraph["id"], "detail": "Possible greeting or channel chatter."})
            advance()
    if source.get("uncertain_audio_spans"):
        issues.append({"code": "unresolved_source_audio", "item_id": "document",
                       "detail": "The source has unresolved audio spans; writing cannot recover missing or disputed speech."})
    return {"state": "needs_review" if issues else "source_consistent", "externally_fact_checked": False,
            "scientific_accuracy_guaranteed": False, "assessments": assessments, "issues": issues,
            "factual_risk_assessments": factual_risks,
            "similarity_checks": similarity_checks, "similarity_policy": {"consecutive_tokens": 12, "matched_fraction": .8},
            "limitations": ["Model review checks source consistency; it is not independent factual verification.",
                            "A separate model plausibility screen can flag source errors but cannot prove scientific truth.",
                            "Similarity heuristics are not a plagiarism or copyright determination.",
                            "An educator must check scientific claims and unresolved source evidence before publication."]}
