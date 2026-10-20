"""CLI orchestration. HTTP jobs use the same downloader and M1 pipeline."""
from pathlib import Path

from ..config import Settings
from ..ingestion_config import IngestionSettings
from ..pipeline import run_pipeline
from .audio_service import duration
from .document_service import write_json
from .youtube_service import IngestionError, canonicalize_youtube_url, download_audio


def run_youtube_pipeline(url: str, output: Path, settings: Settings, limits: IngestionSettings,
                         authorized: bool, keep_chunks=False, on_progress=None):
    canonical = canonicalize_youtube_url(url)
    if not authorized:
        raise IngestionError("authorization_required", "Add --authorized to confirm you may process this video.")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    status = {"state": "ingesting", "url": canonical, "audio_verified": False}
    write_json(output / "ingestion.json", status)
    try:
        source, metadata = download_audio(canonical, output / "download", limits, authorized=True)
        if duration(source) > limits.max_duration:
            raise IngestionError("duration_limit", "Downloaded audio exceeds the configured duration limit.")
        status.update(state="transcribing", metadata=metadata)
        write_json(output / "ingestion.json", status)
        path = run_pipeline(source, output / "transcription", settings,
                            keep_chunks=keep_chunks, on_progress=on_progress, max_duration=limits.max_duration)
        status["state"] = "completed"
        write_json(output / "ingestion.json", status)
        return path
    except BaseException as exc:
        status.update(state="failed", error={"code": getattr(exc, "code", "processing_failed"),
                                            "message": str(exc)[:2000]})
        write_json(output / "ingestion.json", status)
        raise
