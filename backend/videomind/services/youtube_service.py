"""Strict video parsing and a bounded, isolated yt-dlp download process."""
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit

from ..ingestion_config import IngestionSettings


class IngestionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonicalize_youtube_url(url: str) -> str:
    def invalid():
        raise IngestionError("invalid_url", "Use a single YouTube watch, shorts, embed, or youtu.be video URL.")

    if not isinstance(url, str) or len(url) > 2048 or re.search(r"[\s\\\x00-\x1f\x7f]", url):
        invalid()
    try:
        parts = urlsplit(url)
        if (parts.scheme not in {"https", "http"} or parts.username is not None
                or parts.password is not None or parts.port is not None or parts.fragment):
            invalid()
        host = parts.hostname
        query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=20)
    except ValueError:
        invalid()
    if "list" in query or "index" in query:
        raise IngestionError("playlist_not_supported", "Playlists are not supported; supply only the video URL.")
    if host in {"youtu.be", "www.youtu.be"}:
        match = re.fullmatch(r"/([A-Za-z0-9_-]{11})/?", parts.path)
        video_id = match.group(1) if match else ""
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parts.path == "/watch":
            values = query.get("v", [])
            video_id = values[0] if len(values) == 1 else ""
        else:
            match = re.fullmatch(r"/(?:shorts|embed)/([A-Za-z0-9_-]{11})/?", parts.path)
            video_id = match.group(1) if match else ""
    else:
        invalid()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        invalid()
    # Discard tracking parameters; never pass user-supplied options to yt-dlp.
    return f"https://www.youtube.com/watch?v={video_id}"


def download_audio(url: str, destination: Path, settings: IngestionSettings,
                   authorized: bool, check_cancel=lambda: None) -> tuple[Path, dict]:
    canonical = canonicalize_youtube_url(url)
    if not authorized:
        raise IngestionError("authorization_required", "Confirm that you are authorized to process this video.")
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    limits = asdict(settings)
    limits["storage_dir"] = str(settings.storage_dir)
    payload = json.dumps({"url": canonical, "destination": str(destination.resolve()), "limits": limits})
    process = None
    succeeded = False
    try:
        check_cancel()
        process = subprocess.Popen(
            [sys.executable, "-m", "videomind.download_worker"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.monotonic() + settings.download_timeout
        first = True
        while True:
            check_cancel()
            if time.monotonic() >= deadline:
                raise IngestionError("download_timeout", "YouTube download timed out. Try an authorized audio upload.")
            try:
                stdout, _ = process.communicate(input=payload if first else None, timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                first = False
        try:
            result = json.loads(stdout)
        except (ValueError, TypeError) as exc:
            raise IngestionError("download_failed", "The downloader failed. Try an authorized audio upload.") from exc
        if process.returncode or not result.get("ok"):
            raise IngestionError(result.get("code", "download_failed"), result.get("message", "Download failed."))
        path = destination / "source.audio"
        if not path.is_file() or not 0 < path.stat().st_size <= settings.max_bytes:
            raise IngestionError("invalid_download", "The downloader did not produce a usable bounded audio file.")
        succeeded = True
        return path, result["metadata"]
    except OSError as exc:
        raise IngestionError("download_failed", "Unable to start or save the audio download.") from exc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
        # Only downloader-owned partial files are removed. Sanitized metadata is retained.
        if not succeeded:
            for name in ("source.audio", "source.audio.part", "source.audio.ytdl"):
                (destination / name).unlink(missing_ok=True)
