"""Direct rewriting by default, plus the explicitly selected historical review pipeline."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from .content_service import prepare_document_source
from .document_service import write_json, write_text, export_docx
from .ollama_service import OllamaClient, ModelSession
from .understanding_service import build_evidence, extract_knowledge
from .rewriting_service import write_explanation
from .quality_service import check_quality
from .verification_service import load_primary, sha256
from .knowledge_reuse_service import load_reusable_knowledge
from .model_reuse_service import SavedModelCalls
from .content_gate_service import make_reading_copy


def load_source(source):
    if (source / "verified_transcript.json").is_file():
        report = json.loads((source / "verification.json").read_text())
        if report.get("state") not in {"completed", "completed_with_errors"}:
            raise ValueError("Document writing requires a completed verification report")
        reviewed = json.loads((source / "verified_transcript.json").read_text())
        prepared = prepare_document_source(reviewed)
        saved = source / "document_source.json"
        if saved.is_file() and json.loads(saved.read_text()) != prepared:
            raise ValueError("Prepared source does not match the preserved verification transcript")
        return prepared
    _, raw, _, _, _, _ = load_primary(source)
    reviewed = dict(raw, words=[dict(word, verification_status="not_checked", audio_reviewed=False) for word in raw["words"]])
    return prepare_document_source(reviewed)


def attribution_for(source, title=None, url=None, creator=None):
    metadata = {}
    for path in (source.parent / "download" / "metadata.json", source.parent / "ingestion.json"):
        if path.is_file():
            value = json.loads(path.read_text())
            metadata.update(value.get("metadata", value))
    result = {"title": title or metadata.get("title") or source.name,
              "url": url or metadata.get("webpage_url") or metadata.get("url"),
              "creator": creator or metadata.get("channel") or metadata.get("uploader")}
    for key, value in result.items():
        if value is not None and (not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value)):
            raise ValueError("Invalid source attribution")
    if result["url"]:
        parsed = urlsplit(result["url"])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Source attribution URL must be HTTP(S) without credentials; it is never fetched")
    return result


def generate_reviewed_document(source: Path, output: Path, settings, client=None, *, title=None, url=None, creator=None,
                      check_cancel=lambda: None, on_progress=lambda stage, percent: None, reuse_knowledge=None,
                      reuse_model_calls=None):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError("Document output must be outside the original source directory")
    if output.exists():
        raise ValueError("Use a new document output directory; existing runs are immutable")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if not files or len(files) > 10000:
        raise ValueError("Missing or oversized source evidence directory")
    # Bound JSON/text loading; audio hashing is streamed and does not decode audio.
    if sum(path.stat().st_size for path in files if path.suffix in {".json", ".txt"}) > 64_000_000:
        raise ValueError("Source text/evidence exceeds 64 MB input limit")
    hashes = {str(path.relative_to(source)): sha256(path) for path in files}
    prepared = load_source(source)
    evidence, batches = build_evidence(prepared, settings.chunk_chars)
    if not batches:
        raise ValueError("No technical source material remains after editorial preparation")
    if len(batches) > settings.max_chunks:
        raise ValueError("Source exceeds configured extraction chunk limit; no material was silently dropped")
    attribution = attribution_for(source, title, url, creator)
    reused, reuse_audit = None, None
    if reuse_knowledge is not None:
        prior = Path(reuse_knowledge).resolve()
        if prior == output or prior in output.parents:
            raise ValueError("New output must be outside the reused extraction directory")
        reused, reuse_audit = load_reusable_knowledge(prior, hashes, prepared, evidence, batches, settings)
    if reuse_model_calls is not None and (Path(reuse_model_calls).resolve() == output or Path(reuse_model_calls).resolve() in output.parents):
        raise ValueError("New output must be outside the saved model-call directory")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest = {"kind": "educational_document", "schema_version": 1, "state": "created",
                "created_at": datetime.now(timezone.utc).isoformat(), "settings": asdict(settings),
                "source_artifacts_sha256": hashes, "source_directory": str(source), "attribution": attribution,
                "raw_transcript_modified": False, "externally_fact_checked": False}
    if reuse_audit:
        manifest["reused_extraction"] = reuse_audit
    write_json(output / "manifest.json", manifest)
    saved_calls = None

    def integrity():
        current = sorted(path for path in source.rglob("*") if path.is_file())
        source_ok = {str(path.relative_to(source)): sha256(path) for path in current} == hashes
        reuse_ok = not reuse_audit or all((Path(reuse_audit["directory"]) / name).is_file() and
            sha256(Path(reuse_audit["directory"]) / name) == digest for name, digest in reuse_audit["artifacts_sha256"].items())
        return source_ok and reuse_ok and (saved_calls is None or saved_calls.unchanged())

    def stage(name, percent):
        check_cancel()
        manifest["stage"] = name
        write_json(output / "manifest.json", manifest)
        on_progress(name, percent)

    try:
        write_json(output / "prepared_source.json", prepared)
        write_json(output / "evidence.json", {"source": attribution, "passages": evidence})
        client = client if client is not None else OllamaClient(settings)
        stage("reusing_knowledge" if reused else "extracting_knowledge", 5)
        manifest["ollama"] = client.metadata()
        if reuse_model_calls is not None:
            saved_calls = SavedModelCalls(reuse_model_calls, hashes, prepared, evidence, manifest["ollama"])
            manifest["reused_model_calls_directory"] = str(saved_calls.directory)
        session = ModelSession(client, settings, output / "model_calls", check_cancel, saved_calls)
        knowledge = reused if reused is not None else extract_knowledge(session, batches, settings.max_concepts,
            on_batch=lambda done, total: stage("extracting_knowledge", 5 + int(29 * done / total)))
        write_json(output / "knowledge.json", knowledge)
        stage("writing", 35)
        document = write_explanation(session, knowledge,
            on_progress=lambda done, total: stage("writing", 35 + int(29 * done / total)))
        write_json(output / "document.json", document)
        stage("reviewing_claims", 65)
        quality = check_quality(session, knowledge, document, evidence, prepared,
            on_progress=lambda done, total: stage("reviewing_claims", 65 + int(29 * done / total)))
        write_json(output / "quality.json", quality)
        stage("checking_editorial_content", 94)
        reading, content_gate = make_reading_copy(session, document, knowledge, quality)
        write_json(output / "reading_document.json", reading)
        write_json(output / "content_gate.json", content_gate)
        quality["content_gate"] = reading["content_gate"]
        if content_gate["withheld"]:
            quality["state"] = "needs_review"
            quality["issues"].append({"code": "content_withheld", "item_id": "document",
                "detail": f"{len(content_gate['withheld'])} candidate paragraphs were withheld. This reading copy is incomplete; consult content_gate.json and the original candidate."})
        write_json(output / "quality.json", quality)
        if client.metadata().get("digest") != manifest["ollama"].get("digest"):
            raise ValueError("Ollama model changed during generation; retry in a new output directory")
        if not integrity():
            raise ValueError("Source artifacts changed during document generation")
        stage("exporting_docx", 95)
        # A separate, readable draft; uncertainty and quality findings are also in Word.
        text = document["title"] + "\n\nSource: " + attribution["title"] + "\nStatus: " + quality["state"] + "\n"
        text += f"Withheld candidate paragraphs: {len(content_gate['withheld'])}. This reading copy does not establish complete lecture coverage.\n"
        by_id = {item["id"]: item for item in knowledge["concepts"]}
        for section in reading["sections"]:
            text += "\n" + section["heading"] + "\n\n"
            for paragraph in section["paragraphs"]:
                refs = sorted({citation["evidence_id"] for key in paragraph["concept_ids"] for citation in by_id[key]["citations"]})
                text += paragraph["text"] + " [S1: " + ", ".join(refs) + "]\n\n"
        from collections import Counter
        text += "\nContent integrity findings (full candidate and reasons retained separately):\n" + "\n".join(
            f"{code}: {count}" for code, count in sorted(Counter(issue['code'] for issue in quality['issues']).items()))
        write_text(output / "document.txt", text + "\n")
        export_docx(output / "document.docx", reading, knowledge, evidence, quality, attribution)
        if not integrity():
            raise ValueError("Source artifacts changed during Word export")
        manifest.update(state="completed", quality_state=quality["state"], model_calls=session.calls,
                        source_artifacts_unchanged=True, artifacts=["document.docx", "document.txt", "document.json",
                            "knowledge.json", "quality.json", "evidence.json", "prepared_source.json",
                            "outline.json", "reading_document.json", "content_gate.json", "model_calls"])
        if reuse_audit:
            write_json(output / "reuse_integrity.json", reuse_audit)
            manifest["artifacts"].append("reuse_integrity.json")
        else:
            manifest["artifacts"].append("extraction_validation.json")
        if saved_calls is not None:
            manifest["replayed_model_calls"] = len(saved_calls.used)
            if saved_calls.used:
                manifest["artifacts"].append("model_reuse.json")
        write_json(output / "integrity.json", {"source_artifacts_unchanged": True, "sha256": hashes})
        write_json(output / "manifest.json", manifest)
        on_progress("completed", 100)
        return output / "document.docx"
    except BaseException as exc:
        unchanged = integrity()
        manifest.update(state="failed", error_type=type(exc).__name__, error=str(exc), source_artifacts_unchanged=unchanged)
        write_json(output / "manifest.json", manifest)
        write_json(output / "integrity.json", {"source_artifacts_unchanged": unchanged, "sha256": hashes})
        # Only this new run's final deliverable is withdrawn on failure; evidence remains.
        (output / "document.docx").unlink(missing_ok=True)
        raise


def generate_document(source, output, settings, client=None, *, pipeline="direct", **kwargs):
    """Default to transcript rewriting; legacy extraction is explicitly opt-in."""
    if pipeline == "legacy":
        return generate_reviewed_document(source, output, settings, client, **kwargs)
    if pipeline != "direct":
        raise ValueError("Unknown writing pipeline")
    from .direct_rewrite_service import rewrite_document
    return rewrite_document(source, output, settings, client, **kwargs)
