import math
from pathlib import Path

from ..config import Settings
from ..models import Chunk
from .audio_service import run_media


def plan_chunks(duration: float, settings: Settings) -> list[Chunk]:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    size, pad = settings.chunk_seconds, settings.overlap_seconds
    return [
        Chunk(i, i * size, min((i + 1) * size, duration),
              max(0, i * size - pad), min((i + 1) * size + pad, duration))
        for i in range(math.ceil(duration / size))
    ]


def extract_chunk(source: Path, target: Path, chunk: Chunk, timeout: float):
    run_media([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
        "-protocol_whitelist", "file,pipe", "-ss", str(chunk.audio_start),
        "-i", str(source), "-t", str(chunk.audio_end - chunk.audio_start),
        "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target),
    ], timeout)
