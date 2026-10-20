import json
import math
from pathlib import Path
import subprocess


class AudioError(RuntimeError):
    pass


# Reject playlists/concat demuxers that can reference other local files or URLs.
MEDIA_FORMATS = "wav,mp3,flac,ogg,mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,aac,aiff,amr,au"


def run_media(args: list[str], timeout: float) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioError(f"Media tool failed ({args[0]}): {exc}") from exc
    if result.returncode:
        raise AudioError(f"{args[0]} rejected media: {result.stderr[-2000:].strip()}")
    return result.stdout


def duration(path: Path, timeout: float = 60) -> float:
    if not path.is_file():
        raise AudioError(f"Input is not a file: {path}")
    # No network/nested playlist protocols; CLI input must be a local file.
    output = run_media([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", MEDIA_FORMATS,
        "-select_streams", "a:0", "-show_entries", "stream=codec_type:format=duration",
        "-of", "json", str(path.resolve()),
    ], timeout)
    try:
        info = json.loads(output)
        seconds = float(info["format"]["duration"])
        if not info.get("streams") or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("missing audio or invalid duration")
    except (KeyError, TypeError, ValueError) as exc:
        raise AudioError("Input has no decodable audio with finite positive duration") from exc
    return seconds


def normalize(source: Path, target: Path, timeout: float, max_duration: float | None = None) -> float:
    source_duration = duration(source)
    if max_duration is not None and source_duration > max_duration:
        raise AudioError("Audio exceeds the configured duration limit")
    run_media([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
        "-protocol_whitelist", "file,pipe", "-format_whitelist", MEDIA_FORMATS,
        "-i", str(source.resolve()), "-map", "0:a:0",
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-rf64", "auto",
        *(["-t", str(max_duration + 0.1)] if max_duration is not None else []),
        str(target),
    ], timeout)
    seconds = duration(target)
    if max_duration is not None and seconds > max_duration:
        raise AudioError("Decoded audio exceeds the configured duration limit")
    return seconds
