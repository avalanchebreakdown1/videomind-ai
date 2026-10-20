"""Isolated yt-dlp runner. Never prints signed URLs, cookies or raw extractor errors."""
import json
import math
from pathlib import Path
import sys
import urllib.error
import urllib.request

from .services.document_service import write_json
from .services.network_service import build_public_opener, validate_network_url
from .services.youtube_service import IngestionError, canonicalize_youtube_url


def safe_metadata(info: dict, canonical: str, max_duration: float) -> dict:
    if (info.get("_type", "video") != "video" or info.get("id") != canonical.rsplit("=", 1)[1]
            or info.get("extractor_key", "").lower() != "youtube"):
        raise IngestionError("unsupported_source", "Only single YouTube videos are supported.")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise IngestionError("live_not_supported", "Live or unfinished videos are not supported.")
    if info.get("availability") not in {None, "public", "unlisted"} or (info.get("age_limit") or 0) >= 18:
        raise IngestionError("restricted_video", "This video requires restricted access. Use an authorized local audio copy.")
    seconds = info.get("duration")
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= max_duration:
        raise IngestionError("duration_limit", "The video has an unknown duration or exceeds the configured duration limit.")
    return {
        "id": info["id"], "url": canonical, "title": str(info.get("title") or "Untitled")[:1000],
        "channel": str(info.get("channel") or info.get("uploader") or "")[:500],
        "duration_seconds": seconds, "license": str(info.get("license") or "Not specified")[:500],
        "upload_date": str(info.get("upload_date") or "")[:20],
        "authorization": "user_confirmed", "audio_verified": False,
    }


def run_download(payload: dict) -> dict:
    from yt_dlp import YoutubeDL
    from yt_dlp.globals import plugin_dirs
    from yt_dlp.networking.common import Request, Response
    from yt_dlp.networking.exceptions import HTTPError, TransportError

    # This runs in an isolated child: never auto-load machine-local yt-dlp plugins.
    plugin_dirs.value = []

    class Logger:
        def debug(self, message): pass
        def warning(self, message): pass
        def error(self, message): pass

    class GuardedYoutubeDL(YoutubeDL):
        def urlopen(self, request):
            if isinstance(request, str):
                request = Request(request)
            validate_network_url(request.url)
            headers = dict(self.params.get("http_headers", {})) | dict(request.headers)
            headers = {key: value for key, value in headers.items() if key.lower() != "accept-encoding"}
            headers["Accept-Encoding"] = "identity"
            network_request = urllib.request.Request(request.url, data=request.data,
                                                      headers=headers, method=request.method)
            try:
                raw = build_public_opener(self.cookiejar).open(network_request, timeout=socket_timeout)
                return Response(raw, raw.url, raw.headers, raw.status)
            except urllib.error.HTTPError as exc:
                raise HTTPError(Response(exc, exc.url, exc.headers, exc.code)) from exc
            except (OSError, urllib.error.URLError) as exc:
                raise TransportError("YouTube network request failed") from exc

    canonical = canonicalize_youtube_url(payload["url"])
    folder, limits = Path(payload["destination"]), payload["limits"]
    max_bytes, socket_timeout = limits["max_bytes"], limits["socket_timeout"]

    def enforce_size(progress):
        if max(progress.get("downloaded_bytes") or 0, progress.get("total_bytes") or 0) > max_bytes:
            raise IngestionError("source_too_large", "The audio exceeds the configured size limit.")

    options = {
        "format": "bestaudio[protocol=https][vcodec=none]", "outtmpl": str(folder / "source.audio"),
        "noplaylist": True, "allowed_extractors": ["youtube"], "geo_bypass": False,
        "socket_timeout": socket_timeout, "retries": 2, "fragment_retries": 0,
        "extractor_retries": 1, "cachedir": False, "quiet": True, "noprogress": True,
        "logger": Logger(), "progress_hooks": [enforce_size], "max_filesize": max_bytes,
        "buffersize": 65536, "noresizebuffer": True, "http_chunk_size": 0, "nopart": False,
        "overwrites": False, "fixup": "never", "proxy": "",
        "js_runtimes": {}, "remote_components": [],
        "usenetrc": False, "cookiefile": None, "cookiesfrombrowser": None,
    }
    with GuardedYoutubeDL(options) as downloader:
        info = downloader.extract_info(canonical, download=False)
        metadata = safe_metadata(info, canonical, limits["max_duration"])
        write_json(folder / "metadata.json", metadata)
        if (info.get("vcodec") != "none" or info.get("acodec") in (None, "none")
                or info.get("protocol") != "https" or info.get("requested_formats")):
            raise IngestionError("audio_unavailable", "No supported direct audio-only stream is accessible. Try an audio upload.")
        validate_network_url(info.get("url", ""))
        if (info.get("filesize") or info.get("filesize_approx") or 0) > max_bytes:
            raise IngestionError("source_too_large", "The audio exceeds the configured size limit.")
        downloader.process_info(info)
    target = folder / "source.audio"
    if not target.is_file() or not 0 < target.stat().st_size <= max_bytes:
        raise IngestionError("download_failed", "The audio download was incomplete or exceeded its size limit.")
    return {"ok": True, "metadata": metadata}


def main():
    try:
        payload = json.loads(sys.stdin.read(16384))
        result = run_download(payload)
    except IngestionError as exc:
        result = {"ok": False, "code": exc.code, "message": str(exc)}
    except Exception:
        result = {"ok": False, "code": "download_failed", "message": (
            "YouTube audio is unavailable or the network/download failed. "
            "No access restrictions were bypassed. Try an authorized audio upload.")}
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
