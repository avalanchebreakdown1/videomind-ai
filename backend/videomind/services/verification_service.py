"""Selective audio review. Never edits primary artifacts or silently replaces words."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path

from ..config import Settings
from ..models import Chunk, Word
from ..verification_config import VerificationSettings
from .audio_service import duration
from .chunking_service import extract_chunk
from .document_service import write_json, write_text
from .stitching_service import LEGACY_VERSION, STITCHING_VERSION, render_text, stitch
from .text_service import COMPARISON_VERSION, normalized_token
from .transcription_service import FasterWhisperTranscriber
from .content_service import prepare_document_source


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checkpoint(model: str, cache_dir: str) -> dict:
    name = model.lower().removeprefix("systran/faster-whisper-")
    if name == "large":
        name = "large-v3"
    local = Path(model).expanduser()
    weights = local / "model.bin"
    if not weights.is_file():
        folder = Path(cache_dir) / f"models--Systran--faster-whisper-{name}"
        ref = folder / "refs/main"
        candidates = [folder / "snapshots" / ref.read_text().strip() / "model.bin"] if ref.is_file() else list(folder.glob("snapshots/*/model.bin"))
        weights = candidates[0] if len(candidates) == 1 else Path("/nonexistent-videomind-model")
    return {"model": local.name if local.is_dir() else name,
            "weights_sha256": sha256(weights) if weights.is_file() else None}


def require_distinct(primary: str, secondary: str, primary_cache: str, secondary_cache: str):
    first, second = checkpoint(primary, primary_cache), checkpoint(secondary, secondary_cache)
    both_hashes = first["weights_sha256"] is not None and second["weights_sha256"] is not None
    same_checkpoint = (first["weights_sha256"] == second["weights_sha256"] if both_hashes
                       else first["model"] == second["model"])
    if same_checkpoint:
        raise ValueError("Verification requires a different ASR checkpoint from the primary model")
    return first, second


def select_sections(words: list[Word], raw_chunks: list[dict], chunks: list[Chunk],
                    seconds: float, config: VerificationSettings, stitching_issues=None) -> tuple[list[dict], int]:
    tiles = {}
    count = math.ceil(seconds / config.section_seconds)

    def flag(start, end, reason, priority):
        start, end = max(0, min(start, seconds)), max(0, min(end, seconds))
        if end < start:
            return
        first = min(count - 1, int(start / config.section_seconds))
        last = min(count - 1, int(max(start, math.nextafter(end, -math.inf)) / config.section_seconds))
        for tile in range(first, last + 1):
            entry = tiles.setdefault(tile, {"priority": priority, "reasons": set()})
            entry["priority"] = min(entry["priority"], priority)
            entry["reasons"].add(reason)

    for word in words:
        if word.probability < config.word_threshold:
            flag(word.start, word.end, "low_word_probability", 0)
    for issue in stitching_issues or []:
        flag(issue["start"], issue["end"], "stitching_uncertainty", 0)
    tokens = [normalized_token(word.text) for word in words]
    for i in range(1, len(words)):
        if tokens[i] and tokens[i] == tokens[i - 1]:
            flag(words[i - 1].start, words[i].end, "repetition", 1)
    for i in range(3, len(words) - 2):
        if tokens[i - 3:i] == tokens[i:i + 3]:
            flag(words[i - 3].start, words[i + 2].end, "repetition", 1)
    for raw in raw_chunks:
        offset = raw["chunk"]["audio_start"]
        if not raw["words"]:
            flag(raw["chunk"]["core_start"], raw["chunk"]["core_end"], "empty_primary_chunk", 1)
        for segment in raw["segments"]:
            if (segment.get("avg_logprob", 0) < -0.8 or segment.get("compression_ratio", 0) > 2.4
                    or segment.get("no_speech_prob", 0) > 0.6):
                flag(offset + segment["start"], offset + segment["end"], "suspicious_segment_metrics", 1)
    for chunk in chunks[1:]:
        flag(chunk.core_start - 2, chunk.core_start + 2, "chunk_boundary", 2)
    previous = 0
    for word in words:
        if word.start - previous >= config.gap_seconds:
            flag(previous, word.start, "untranscribed_gap", 3)
        previous = max(previous, word.end)
    if seconds - previous >= config.gap_seconds:
        flag(previous, seconds, "untranscribed_gap", 3)
    # Audit high-confidence material too; suspicion alone cannot find confident errors.
    for tile in {0, count // 2, count - 1}:
        flag(tile * config.section_seconds, min((tile + 1) * config.section_seconds, seconds), "routine_audio_audit", 4)
    chosen = sorted(tiles, key=lambda tile: (tiles[tile]["priority"], tile))[:config.max_sections]
    result = [{"index": i, "start": tile * config.section_seconds,
               "end": min((tile + 1) * config.section_seconds, seconds),
               "reasons": sorted(tiles[tile]["reasons"])} for i, tile in enumerate(sorted(chosen))]
    return result, len(tiles) - len(chosen)


def compare_candidates(primary: list[Word], candidate: list[Word], threshold: float, tolerance: float = 1) -> dict:
    matcher = SequenceMatcher(None, [normalized_token(w.text) for w in primary],
                              [normalized_token(w.text) for w in candidate], autojunk=False)
    uncertain, supported, differences = set(), set(), []
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(a, b), range(c, d)):
                timing_matches = (candidate[j].end + tolerance >= primary[i].start
                                  and primary[i].end + tolerance >= candidate[j].start)
                if candidate[j].probability >= threshold and timing_matches:
                    supported.add(i)
                else:
                    uncertain.add(i)
                if not timing_matches:
                    differences.append({"operation": "timing_mismatch", "primary_indices": [i],
                                        "primary_text": primary[i].text, "candidate_text": candidate[j].text,
                                        "candidate_words": [asdict(candidate[j])]})
        else:
            uncertain.update(range(a, b))
            differences.append({"operation": tag, "primary_indices": list(range(a, b)),
                                "primary_text": render_text(primary[a:b]),
                                "candidate_text": render_text(candidate[c:d]),
                                "candidate_words": [asdict(word) for word in candidate[c:d]]})
    return {"supported_indices": sorted(supported), "uncertain_indices": sorted(uncertain),
            "disagreements": differences,
            "needs_review": bool(differences or uncertain or not primary and not candidate),
            "empty_both": not primary and not candidate}


def primary_artifacts(run: Path) -> list[Path]:
    paths = [run / name for name in ("manifest.json", "raw_transcript.txt", "raw_transcript.json", "chunks.json")]
    paths.extend(sorted((run / "raw_chunks").glob("*.json")))
    if (run / "stitching.json").is_file():
        paths.append(run / "stitching.json")
    if (run / "restitching.json").is_file():
        paths.append(run / "restitching.json")
    if any(not path.is_file() for path in paths):
        raise ValueError("Missing primary transcription evidence")
    return paths


def load_primary(run: Path):
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest.get("state") != "completed" or manifest.get("kind") != "raw_transcript":
        raise ValueError("Verification requires a completed raw transcription run")
    chunks = [Chunk(**item) for item in json.loads((run / "chunks.json").read_text())]
    raw_chunks = [json.loads(path.read_text()) for path in sorted((run / "raw_chunks").glob("*.json"))]
    from ..models import Transcript
    transcripts = [Transcript(Chunk(**raw["chunk"]), [Word(**word) for word in raw["words"]],
                              raw["segments"], raw["language"], raw["language_probability"]) for raw in raw_chunks]
    version = manifest.get("stitching_version", LEGACY_VERSION)
    words = stitch(transcripts, chunks, version=version)
    if version == STITCHING_VERSION and not (run / "stitching.json").is_file():
        raise ValueError("Missing versioned stitching evidence")
    if any(not 0 <= word.probability <= 1 for word in words):
        raise ValueError("Invalid primary word probability")
    raw = json.loads((run / "raw_transcript.json").read_text())
    if ([asdict(word) for word in words] != raw["words"] or render_text(words) != raw["text"]
            or (run / "raw_transcript.txt").read_text(encoding="utf-8") != raw["text"] + "\n"):
        raise ValueError("Primary transcript and original chunk evidence do not match")
    seconds = duration(run / "normalized.wav")
    if abs(seconds - manifest["duration_seconds"]) > 0.05 or abs(chunks[-1].core_end - seconds) > 0.05:
        raise ValueError("Normalized audio duration does not match primary evidence")
    return manifest, raw, words, chunks, raw_chunks, seconds


def verify_run(run: Path, output: Path, settings: Settings, config: VerificationSettings,
               transcriber=None, check_cancel=lambda: None, on_progress=None) -> Path:
    run, output = run.resolve(), output.resolve()
    if output == run or run in output.parents:
        raise ValueError("Verification output must be outside the original transcription directory")
    artifacts = primary_artifacts(run)
    hashes = {str(path.relative_to(run)): sha256(path) for path in artifacts}
    manifest, raw, words, chunks, raw_chunks, seconds = load_primary(run)
    first, second = require_distinct(manifest["settings"]["model"], config.model,
                                     manifest["settings"]["model_dir"], settings.model_dir)
    stitching_issues = raw.get("stitching_issues", [])
    plan, omitted = select_sections(words, raw_chunks, chunks, seconds, config, stitching_issues)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    (output / "sections").mkdir()
    report = {
        "schema_version": 1, "state": "running", "progress": 0,
        "comparison_version": COMPARISON_VERSION,
        "source_stitching_version": manifest.get("stitching_version", LEGACY_VERSION),
        "kind": "audio_verification", "scope": "selected_sections", "audio_verified": False,
        "audio_verification_performed": False, "all_audio_checked": False,
        "primary_checkpoint": first, "secondary_checkpoint": second,
        "settings": asdict(config) | {"model": second["model"]}, "source_artifacts_sha256": hashes,
        "source_audio_sha256": sha256(run / "normalized.wav"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_sections": plan, "omitted_candidate_sections": omitted, "sections": [],
        "source_stitching_issues": stitching_issues,
        "warnings": ["Selective audio review is not proof of complete or correct transcription.",
                     "Different Whisper checkpoints share a model family and can make correlated errors.",
                     "Original wording is retained. Disagreements require human review; no automatic corrections."],
    }
    statuses = ["uncertain" if any(issue["start"] <= midpoint <= issue["end"] for issue in stitching_issues)
                else "not_checked" for word in words for midpoint in [(word.start + word.end) / 2]]
    audio_reviewed = set()

    def save():
        report["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "manifest.json", {key: value for key, value in report.items() if key != "sections"})
        write_json(output / "verification.json", report)
        if on_progress:
            on_progress(report["progress"])

    engine = transcriber if transcriber is not None else FasterWhisperTranscriber(
        replace(settings, model=config.model, language=manifest["settings"].get("language")))
    try:
        save()
        for section in plan:
            check_cancel()
            indices = [i for i, word in enumerate(words)
                       if section["start"] <= (word.start + word.end) / 2 < section["end"]
                       or section["end"] == seconds and (word.start + word.end) / 2 == seconds]
            primary = [words[i] for i in indices]
            evidence = {**section, "primary_word_indices": indices, "primary_text": render_text(primary), "passes": []}
            folder = output / "sections" / f"{section['index']:06d}"
            folder.mkdir()
            try:
                for pass_index in range(2 if config.recheck else 1):
                    check_cancel()
                    pad = config.context_seconds if pass_index == 0 else config.recheck_context_seconds
                    chunk = Chunk(section["index"], section["start"], section["end"],
                                  max(0, section["start"] - pad), min(seconds, section["end"] + pad))
                    if pass_index and evidence["passes"]:
                        first_audio = evidence["passes"][0]["audio_chunk"]
                        if chunk.audio_start == first_audio["audio_start"] and chunk.audio_end == first_audio["audio_end"]:
                            evidence["recheck_skipped"] = "No additional audio context is available."
                            break
                    path = folder / f"pass{pass_index + 1}.wav"
                    attempt_errors = []
                    try:
                        extract_chunk(run / "normalized.wav", path, chunk, settings.process_timeout)
                        for attempt in range(settings.asr_retries + 1):
                            check_cancel()
                            try:
                                candidate = engine.transcribe(path, chunk)
                                break
                            except Exception as exc:
                                attempt_errors.append({"attempt": attempt + 1, "type": type(exc).__name__})
                                if attempt == settings.asr_retries:
                                    raise
                        # Reuse timestamp validation; local core index is zero for this check.
                        if candidate.chunk != chunk:
                            raise ValueError("Verification ASR returned a mismatched audio section")
                        validation_chunk = replace(chunk, index=0)
                        selected = stitch([replace(candidate, chunk=validation_chunk)], [validation_chunk])
                        if section["end"] < seconds:
                            selected = [word for word in selected if (word.start + word.end) / 2 < section["end"]]
                        if any(not 0 <= word.probability <= 1 for word in candidate.words):
                            raise ValueError("Invalid verification word probabilities")
                        current = compare_candidates(primary, selected, config.word_threshold,
                                                     config.alignment_tolerance_seconds)
                        audio_reviewed.update(indices)
                        pass_record = {"pass": pass_index + 1, "context_seconds": pad,
                                       "attempt_errors": attempt_errors, "audio_chunk": asdict(chunk),
                                       "transcript": asdict(candidate), "comparison": current}
                        write_json(folder / f"pass{pass_index + 1}.json", pass_record)
                        evidence["passes"].append(pass_record)
                        if pass_index == 0:
                            for local in current["supported_indices"]:
                                statuses[indices[local]] = "supported_by_second_asr"
                            for local in current["uncertain_indices"]:
                                statuses[indices[local]] = "uncertain"
                        else:
                            # A recheck can expose more uncertainty, never erase earlier conflicting evidence.
                            for local in current["uncertain_indices"]:
                                statuses[indices[local]] = "uncertain"
                        if not current["needs_review"]:
                            break
                    finally:
                        path.unlink(missing_ok=True)
                        if attempt_errors:
                            write_json(folder / f"pass{pass_index + 1}-attempts.json", attempt_errors)
                evidence["status"] = "uncertain" if any(p["comparison"]["needs_review"] for p in evidence["passes"]) else "supported"
            except Exception as exc:
                check_cancel()  # Cancellation must escape rather than become an ASR error.
                evidence.update(status="error", error={"type": type(exc).__name__, "message": "Audio review failed for this section; original wording retained."})
                for i in indices:
                    statuses[i] = "uncertain"
            write_json(folder / "result.json", evidence)
            report["sections"].append(evidence)
            report["progress"] = int(95 * len(report["sections"]) / len(plan))
            save()
        check_cancel()
        if ({str(path.relative_to(run)): sha256(path) for path in artifacts} != hashes
                or sha256(run / "normalized.wav") != report["source_audio_sha256"]):
            raise ValueError("Primary artifacts changed during verification")
        successes = [s for s in report["sections"] if s["passes"]]
        checked_seconds = sum(s["end"] - s["start"] for s in successes)
        errors = sum(s["status"] == "error" for s in report["sections"])
        annotations = []
        for word, status in zip(words, statuses):
            if status == "uncertain":
                prefix = word.text[:len(word.text) - len(word.text.lstrip())]
                annotations.append(prefix + "[uncertain: " + word.text.lstrip() + "]")
            else:
                annotations.append(word.text)
        annotated = "".join(annotations).strip()
        warnings = report["warnings"] + (["Some audio sections could not be reviewed."] if errors else [])
        unresolved = [{"start": s["start"], "end": s["end"], "status": s["status"],
                       "primary_word_indices": s["primary_word_indices"]}
                      for s in report["sections"] if s["status"] != "supported"]
        for issue in stitching_issues:
            cursor = issue["start"]
            for section in successes:
                if section["start"] <= cursor:
                    cursor = max(cursor, section["end"])
            if cursor < issue["end"]:
                unresolved.append({"start": issue["start"], "end": issue["end"],
                    "status": "unreviewed_stitching_issue", "primary_word_indices": [i for i, word in enumerate(words)
                        if issue["start"] <= (word.start + word.end) / 2 <= issue["end"]]})
        result = {"kind": "verified_transcript", "audio_verified": False,
                  "comparison_version": COMPARISON_VERSION,
                  "audio_verification_performed": bool(successes), "text": raw["text"],
                  "annotated_text": annotated, "words": [asdict(word) | {"verification_status": status,
                      "audio_reviewed": i in audio_reviewed} for i, (word, status) in enumerate(zip(words, statuses))],
                  "source_stitching_issues": stitching_issues,
                  "uncertain_audio_spans": unresolved, "warnings": warnings}
        notes = "\n".join(f"[{s['start']:.2f}–{s['end']:.2f}s] {s['status']}; see verification.json for audio candidates."
                          for s in unresolved)
        header = "SELECTIVE AUDIO REVIEW — original wording retained; unchecked audio may contain errors.\n\n"
        write_json(output / "verified_transcript.json", result)
        write_text(output / "verified_transcript.txt", header + annotated + ("\n\nUnresolved audio sections:\n" + notes if notes else "") + "\n")
        document_source = prepare_document_source(result)
        write_json(output / "document_source.json", document_source)
        write_text(output / "document_source.txt", "TECHNICAL DOCUMENT SOURCE — claims not independently fact-checked.\n\n" + document_source["annotated_text"] + "\n")
        report.update(state="completed_with_errors" if errors else "completed", progress=100,
                      audio_verification_performed=bool(successes),
                      all_audio_checked=abs(checked_seconds - seconds) < 0.05 and not errors,
                      checked_audio_seconds=checked_seconds, total_audio_seconds=seconds,
                      coverage_fraction=checked_seconds / seconds, raw_artifacts_unchanged=True,
                      word_counts={status: statuses.count(status) for status in ("supported_by_second_asr", "uncertain", "not_checked")},
                      uncertain_sections=len(unresolved), failed_sections=errors,
                      editorial_preparation=document_source["counts"],
                      artifacts=["verified_transcript.txt", "verified_transcript.json", "verification.json",
                                 "document_source.txt", "document_source.json"])
        # Capture the actual downloaded checkpoint identity after lazy model loading.
        report["secondary_checkpoint"] = checkpoint(config.model, settings.model_dir)
        save()
        return output / "verification.json"
    except BaseException as exc:
        report.update(state="failed", error={"type": type(exc).__name__, "message": "Verification stopped; primary transcript preserved."})
        save()
        raise
