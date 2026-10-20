from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Callable

from .config import Settings
from .services.audio_service import normalize
from .services.chunking_service import extract_chunk, plan_chunks
from .services.document_service import write_json, write_text
from .services.stitching_service import STITCHING_VERSION, render_text, stitch_with_report
from .services.transcription_service import FasterWhisperTranscriber, Transcriber


ALLOWED = {
    "created": {"normalizing", "failed"},
    "normalizing": {"transcribing", "failed"},
    "transcribing": {"stitching", "failed"},
    "stitching": {"completed", "failed"},
    "completed": set(), "failed": set(),
}


def transition(manifest: dict, state: str):
    if state not in ALLOWED[manifest["state"]]:
        raise ValueError(f"Illegal state transition: {manifest['state']} -> {state}")
    manifest["state"] = state


def run_pipeline(source: Path, output: Path, settings: Settings,
                 transcriber: Transcriber | None = None, keep_chunks: bool = False,
                 on_progress: Callable[[dict], None] | None = None,
                 max_duration: float | None = None) -> Path:
    source, output = source.resolve(), output.resolve()
    if not source.is_file():
        raise ValueError(f"Input is not a local file: {source}")
    # Exclusive directory creation prevents accidental overwrite and concurrent run collisions.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1, "state": "created", "progress": 0,
        "source": str(source), "kind": "raw_transcript", "audio_verified": False,
        "settings": asdict(settings), "chunks_completed": 0,
        "stitching_version": STITCHING_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "warnings": ["Primary ASR only. Recognition and boundary timestamp errors may remain."],
    }

    def save():
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "manifest.json", manifest)
        if on_progress:
            on_progress(dict(manifest))

    try:
        save()
        transition(manifest, "normalizing")
        save()
        normalized = output / "normalized.wav"
        seconds = normalize(source, normalized, settings.process_timeout, max_duration=max_duration)
        chunks = plan_chunks(seconds, settings)
        manifest.update(duration_seconds=seconds, chunks_total=len(chunks), progress=5)
        write_json(output / "chunks.json", [asdict(chunk) for chunk in chunks])
        (output / "raw_chunks").mkdir()
        (output / "audio_chunks").mkdir()
        transition(manifest, "transcribing")
        save()
        engine = transcriber if transcriber is not None else FasterWhisperTranscriber(settings)
        transcripts = []
        for chunk in chunks:
            chunk_path = output / "audio_chunks" / f"{chunk.index:06d}.wav"
            try:
                extract_chunk(normalized, chunk_path, chunk, settings.process_timeout)
                for attempt in range(settings.asr_retries + 1):
                    try:
                        transcript = engine.transcribe(chunk_path, chunk)
                        break
                    except Exception:
                        if attempt == settings.asr_retries:
                            raise
                        manifest["retry_count"] = manifest.get("retry_count", 0) + 1
                        save()
                        time.sleep(0.25 * (attempt + 1))
                write_json(output / "raw_chunks" / f"{chunk.index:06d}.json", asdict(transcript))
                transcripts.append(transcript)
                manifest.update(chunks_completed=len(transcripts),
                                progress=5 + int(85 * len(transcripts) / len(chunks)))
                save()
            finally:
                if not keep_chunks:
                    chunk_path.unlink(missing_ok=True)
        transition(manifest, "stitching")
        manifest["progress"] = 95
        save()
        stitched = stitch_with_report(transcripts, chunks)
        words = stitched.words
        stitching_issues = [item for item in stitched.boundaries if item["requires_review"]]
        write_json(output / "stitching.json", {"version": STITCHING_VERSION,
                   "boundaries": stitched.boundaries, "word_count": len(words)})
        if stitching_issues:
            manifest["warnings"].append("Some chunk boundaries require audio review; see stitching.json.")
        text = render_text(words)
        if not text:
            manifest["warnings"].append("No speech recognized. This does not prove the source is silent.")
        write_json(output / "raw_transcript.json", {
            "kind": "raw_transcript", "audio_verified": False,
            "text": text, "words": [asdict(word) for word in words],
            "warnings": manifest["warnings"],
            "stitching_issues": stitching_issues,
        })
        write_text(output / "raw_transcript.txt", text + "\n")
        transition(manifest, "completed")
        manifest.update(progress=100, artifacts=["raw_transcript.txt", "raw_transcript.json"])
        save()
        return output / "raw_transcript.txt"
    except BaseException as exc:
        # Includes Ctrl-C; retain completed raw outputs but never claim the run completed.
        if manifest["state"] != "completed":
            transition(manifest, "failed")
            manifest["error"] = {"type": type(exc).__name__, "message": str(exc)[:2000]}
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_json(output / "manifest.json", manifest)
        raise
