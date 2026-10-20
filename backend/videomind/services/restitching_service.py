"""Rebuild assembled transcripts in a NEW run using preserved original ASR chunks."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from ..models import Chunk, Transcript, Word
from .document_service import write_json, write_text
from .stitching_service import LEGACY_VERSION, STITCHING_VERSION, render_text, stitch_with_report
from .verification_service import load_primary, primary_artifacts, sha256


def restitch_run(source: Path, output: Path) -> Path:
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Rebuilt output must be a new directory outside the original run")
    manifest, raw, old_words, chunks, raw_chunks, _ = load_primary(source)
    inputs = primary_artifacts(source) + [source / "normalized.wav"]
    hashes = {str(path.relative_to(source)): sha256(path) for path in inputs}
    transcripts = [Transcript(Chunk(**item["chunk"]), [Word(**word) for word in item["words"]],
                              item["segments"], item["language"], item["language_probability"]) for item in raw_chunks]
    result = stitch_with_report(transcripts, chunks)
    text = render_text(result.words)
    issues = [boundary for boundary in result.boundaries if boundary["requires_review"]]
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    new_manifest = {**manifest, "state": "restitching", "progress": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(), "stitching_version": STITCHING_VERSION}
    try:
        write_json(output / "manifest.json", new_manifest)
        (output / "raw_chunks").mkdir()
        shutil.copyfile(source / "normalized.wav", output / "normalized.wav")
        shutil.copyfile(source / "chunks.json", output / "chunks.json")
        for path in sorted((source / "raw_chunks").glob("*.json")):
            shutil.copyfile(path, output / "raw_chunks" / path.name)
        warnings = ["Primary ASR only. Recognition errors may remain; rebuilding is not independent audio verification."]
        if issues:
            warnings.append("Some chunk boundaries require audio review; see stitching.json.")
        write_json(output / "stitching.json", {"version": STITCHING_VERSION,
                   "boundaries": result.boundaries, "word_count": len(result.words)})
        write_json(output / "raw_transcript.json", {**raw, "text": text, "words": [asdict(w) for w in result.words],
                   "warnings": warnings, "stitching_issues": issues})
        write_text(output / "raw_transcript.txt", text + "\n")
        if any(sha256(source / name) != value for name, value in hashes.items()):
            raise ValueError("Original evidence changed while rebuilding")
        audit = {"original_artifacts_unchanged": True, "source_artifacts_sha256": hashes,
                 "previous_stitching_version": manifest.get("stitching_version", LEGACY_VERSION),
                 "stitching_version": STITCHING_VERSION, "previous_word_count": len(old_words),
                 "new_word_count": len(result.words), "text_changed": text != raw["text"],
                 "boundaries_requiring_review": len(issues)}
        write_json(output / "restitching.json", audit)
        new_manifest.update(state="completed", progress=100, warnings=warnings,
                            restitched_from=hashes["manifest.json"], updated_at=datetime.now(timezone.utc).isoformat())
        write_json(output / "manifest.json", new_manifest)
        return output / "raw_transcript.txt"
    except BaseException as exc:
        new_manifest.update(state="failed", error={"type": type(exc).__name__, "message": str(exc)[:2000]})
        write_json(output / "manifest.json", new_manifest)
        raise
