"""Thematic writing from a concept graph; the writer does not see the transcript."""
from .knowledge_models import Outline, WrittenSection
from .document_service import write_json


def complete_outline(outline, concepts):
    """Reconcile membership without inventing facts or silently dropping concepts."""
    seen, sections, duplicates = set(), [], []
    for section in outline["sections"]:
        ids = []
        for key in section["concept_ids"]:
            if key not in concepts:
                raise ValueError("Outline has unknown concept IDs")
            if key in seen:
                duplicates.append(key)
            else:
                ids.append(key)
                seen.add(key)
        if ids:
            sections.append(dict(section, concept_ids=ids))
    missing = [key for key in concepts if key not in seen]
    # Original concept titles supply headings; no generated facts or guessed grouping.
    sections.extend({"heading": concepts[key]["topic"], "concept_ids": [key]} for key in missing)
    return dict(outline, sections=sections), {"omitted_concepts_restored": missing,
                                            "duplicate_references_removed": duplicates}


def write_explanation(session, knowledge, on_progress=lambda done, total: None):
    concepts = {item["id"]: item for item in knowledge["concepts"]}
    catalog = {key: value["topic"][:60] for key, value in concepts.items()}
    outline = session.ask("outline", """Plan an original formal educational explanation organized by conceptual
dependencies, not source order. Use every concept ID exactly once. Group related concepts into sections,
at most 8 concepts per section. Provide a descriptive title and technical section headings.
Do not add facts or names absent from the catalog.""", catalog, Outline).model_dump()
    outline, outline_audit = complete_outline(outline, concepts)
    write_json(session.directory.parent / "outline.json", {**outline, "assembly_audit": outline_audit})
    document = {"title": outline["title"], "sections": [], "externally_fact_checked": False,
                "outline_assembly": outline_audit}
    # Small writing groups also bound the source passages needed for paragraph review.
    groups = [dict(section, concept_ids=section["concept_ids"][i:i + 2])
              for section in outline["sections"] for i in range(0, len(section["concept_ids"]), 2)]
    index = 0
    for group_index, section in enumerate(groups, 1):
        selected = [concepts[key] for key in section["concept_ids"]]
        # Exact source quotations are for the reviewer, not the writing model.
        plan = [{key: value for key, value in item.items() if key != "citations"} for item in selected]
        result = session.ask("write", """Write a new formal technical explanation for this section from the
concepts. Synthesize relationships and organize by reasoning, not sentence-by-sentence paraphrasing.
Use only the supplied concepts, preserve their caveats and technical notation exactly.
Use one or two concise paragraphs; do not repeat a concept already explained in the section.
Do not invent examples, calculations, definitions or factual context. Each paragraph must cite its
supporting concept_ids. Do not include inline citation markers; the application adds them.
No greetings, promotions, conversational narration, or claims of external verification.
Never treat caveats about ASR/verification status as properties of the subject being taught.
Do not mention internal concept IDs, evidence IDs, or 'the supplied passages' in the prose.""",
                             {"heading": section["heading"], "concepts": plan}, WrittenSection)
        if {key for paragraph in result.paragraphs for key in paragraph.concept_ids} != set(section["concept_ids"]):
            raise ValueError("Writing omitted or invented concept IDs")
        paragraphs = []
        for paragraph in result.paragraphs:
            if not set(paragraph.concept_ids) <= set(section["concept_ids"]):
                raise ValueError("Writing invented concept IDs")
            index += 1
            paragraphs.append({"id": f"P{index:04d}", **paragraph.model_dump()})
        if document["sections"] and document["sections"][-1]["heading"] == section["heading"]:
            document["sections"][-1]["paragraphs"].extend(paragraphs)
        else:
            document["sections"].append({"heading": section["heading"], "paragraphs": paragraphs})
        write_json(session.directory.parent / "writing_progress.json", document)
        on_progress(group_index, len(groups))
    return document
