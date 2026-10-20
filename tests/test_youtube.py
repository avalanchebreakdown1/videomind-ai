import io
import json
import socket
import subprocess
from urllib.response import addinfourl

import pytest

from videomind.cli import main
from videomind.download_worker import run_download, safe_metadata
from videomind.ingestion_config import IngestionSettings
from videomind.services import network_service, youtube_service
from videomind.services.youtube_service import IngestionError, canonicalize_youtube_url, download_audio


ID = "abcdefghijk"
URL = f"https://www.youtube.com/watch?v={ID}"
STREAM = "https://rr1.googlevideo.com/videoplayback?test=1"


@pytest.mark.parametrize("url", [URL, f"http://youtube.com/watch?v={ID}&t=20",
    f"https://youtu.be/{ID}?si=tracking", f"https://m.youtube.com/watch?v={ID}",
    f"https://www.youtube.com/shorts/{ID}", f"https://youtube.com/embed/{ID}/"])
def test_canonical_urls(url):
    assert canonicalize_youtube_url(url) == URL


@pytest.mark.parametrize("url", [
    "", "not a URL", "file:///etc/passwd", "https://127.0.0.1/watch?v=abcdefghijk",
    "https://youtube.com.evil.test/watch?v=abcdefghijk", "https://evil.test/youtube.com",
    "https://youtube.com@127.0.0.1/watch?v=abcdefghijk", "https://user@youtube.com/watch?v=abcdefghijk",
    "https://youtube.com:443/watch?v=abcdefghijk", "https://youtube.com:bad/watch?v=abcdefghijk",
    "https://youtube.com/watch?v=short", "https://youtube.com/watch?v=abcdefghijk&v=12345678901",
    "https://youtube.com/watch?v=abcdefghijk&list=PL123", "https://youtube.com/playlist?list=PL123",
    "https://youtube.com/live/abcdefghijk", "https://youtu.be/abcdefghijk/extra",
    "https://youtube.com/watch?v=abcdefghijk#fragment", "https://youtube.com\\@evil.test/abcdefghijk",
    " https://youtube.com/watch?v=abcdefghijk", "https://youtube.com/watch?v=abc%0adefghijk",
    "https://youtube.com/watch?v=abcdefghijk\n", "https://[::1]/watch?v=abcdefghijk",
])
def test_invalid_or_unsafe_urls(url):
    with pytest.raises(IngestionError):
        canonicalize_youtube_url(url)


def metadata(**overrides):
    return {"id": ID, "extractor_key": "Youtube", "title": "A lesson", "channel": "Teacher",
            "duration": 14, "availability": "public", "vcodec": "none", "acodec": "opus",
            "protocol": "https", "url": STREAM, "ext": "webm", "format_id": "251",
            "webpage_url": URL, **overrides}


@pytest.mark.parametrize("overrides,code", [
    ({"_type": "playlist"}, "unsupported_source"), ({"id": "other"}, "unsupported_source"),
    ({"extractor_key": "Generic"}, "unsupported_source"), ({"is_live": True}, "live_not_supported"),
    ({"live_status": "is_upcoming"}, "live_not_supported"), ({"availability": "private"}, "restricted_video"),
    ({"availability": "subscriber_only"}, "restricted_video"), ({"age_limit": 18}, "restricted_video"),
    ({"duration": None}, "duration_limit"), ({"duration": float("inf")}, "duration_limit"),
    ({"duration": 99999}, "duration_limit"),
])
def test_metadata_rejections(overrides, code):
    with pytest.raises(IngestionError) as error:
        safe_metadata(metadata(**overrides), URL, 3600)
    assert error.value.code == code


def test_metadata_retains_attribution_but_not_signed_urls():
    result = safe_metadata(metadata(license="Creative Commons", description="secret"), URL, 3600)
    assert result["title"] == "A lesson" and result["license"] == "Creative Commons"
    assert STREAM not in json.dumps(result) and "description" not in result


@pytest.mark.parametrize("url", ["https://evil.test/file", "http://rr1.googlevideo.com/file",
    "https://rr1.googlevideo.com:444/file", "https://rr1.googlevideo.com@evil.test/file",
    "file:///etc/passwd", "https://googlevideo.com.evil.test/file"])
def test_transport_rejects_hosts_and_protocols(url):
    with pytest.raises(IngestionError):
        network_service.validate_network_url(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1", "0.0.0.0", "224.0.0.1", "ff02::1"])
def test_dns_rejects_private_addresses(monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))])
    with pytest.raises(IngestionError, match="non-public"):
        network_service.public_addresses("www.youtube.com", 443)


def test_actual_connection_uses_validated_ip_and_original_tls_host(monkeypatch):
    connections, hosts = [], []
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    class Sock:
        def settimeout(self, timeout): pass
        def connect(self, address): connections.append(address)
        def close(self): pass
    class TLS:
        def wrap_socket(self, sock, server_hostname):
            hosts.append(server_hostname)
            return sock
    monkeypatch.setattr(socket, "socket", lambda *args: Sock())
    connection = network_service.PublicHTTPSConnection("www.youtube.com", timeout=2)
    connection._context = TLS()
    connection.connect()
    assert connections == [("8.8.8.8", 443)] and hosts == ["www.youtube.com"]


def test_redirect_to_arbitrary_host_is_rejected():
    with pytest.raises(IngestionError):
        network_service.SafeRedirectHandler().redirect_request(None, None, 302, "Found", {}, "https://127.0.0.1/private")


def test_authorization_checked_before_process_start(tmp_path):
    with pytest.raises(IngestionError) as error:
        download_audio(URL, tmp_path / "download", IngestionSettings(), authorized=False)
    assert error.value.code == "authorization_required"
    assert not (tmp_path / "download").exists()


def test_downloader_timeout_kills_child_and_cleans_partial(monkeypatch, tmp_path):
    folder = tmp_path / "download"
    class Process:
        returncode = None
        def __init__(self, *args, **kwargs):
            (folder / "source.audio.part").write_bytes(b"partial")
        def communicate(self, *args, **kwargs):
            if kwargs.get("timeout"):
                raise subprocess.TimeoutExpired("download", 0.2)
            return "", ""
        def poll(self): return self.returncode
        def kill(self): self.returncode = -9
    monkeypatch.setattr(youtube_service.subprocess, "Popen", Process)
    times = iter([0, 0, 1000])
    monkeypatch.setattr(youtube_service.time, "monotonic", lambda: next(times))
    with pytest.raises(IngestionError) as error:
        download_audio(URL, folder, IngestionSettings(download_timeout=1), authorized=True)
    assert error.value.code == "download_timeout" and not list(folder.glob("*.part"))


@pytest.mark.parametrize("failure", [False, True])
def test_child_result_protocol_and_partial_cleanup(monkeypatch, tmp_path, failure):
    folder = tmp_path / "download"
    calls = []
    class Process:
        returncode = 1 if failure else 0
        def __init__(self, command, **kwargs):
            calls.append(command)
            (folder / ("source.audio.part" if failure else "source.audio")).write_bytes(b"audio")
            (folder / "metadata.json").write_text('{"title":"Lesson"}')
        def communicate(self, input=None, timeout=None):
            assert json.loads(input)["url"] == URL
            if failure:
                return json.dumps({"ok": False, "code": "restricted_video", "message": "Restricted; try an upload."}), "secret"
            return json.dumps({"ok": True, "metadata": {"title": "Lesson"}}), ""
        def poll(self): return self.returncode
    monkeypatch.setattr(youtube_service.subprocess, "Popen", Process)
    if failure:
        with pytest.raises(IngestionError) as error:
            download_audio(URL, folder, IngestionSettings(), authorized=True)
        assert error.value.code == "restricted_video" and "secret" not in str(error.value)
        assert not (folder / "source.audio.part").exists()
    else:
        path, info = download_audio(URL, folder, IngestionSettings(), authorized=True)
        assert path.read_bytes() == b"audio" and info["title"] == "Lesson"
    assert calls[0][1:] == ["-m", "videomind.download_worker"]
    assert (folder / "metadata.json").exists()


def test_cancellation_kills_downloader(monkeypatch, tmp_path):
    folder, processes = tmp_path / "download", []
    class Process:
        returncode = None
        def __init__(self, *args, **kwargs):
            processes.append(self)
            (folder / "source.audio.part").write_bytes(b"partial")
        def communicate(self, **kwargs): return "", ""
        def poll(self): return self.returncode
        def kill(self): self.returncode = -9
    counter = [0]
    def cancel():
        counter[0] += 1
        if counter[0] == 2:
            raise RuntimeError("cancelled")
    monkeypatch.setattr(youtube_service.subprocess, "Popen", Process)
    with pytest.raises(RuntimeError, match="cancelled"):
        download_audio(URL, folder, IngestionSettings(), authorized=True, check_cancel=cancel)
    assert processes[0].returncode == -9 and not (folder / "source.audio.part").exists()


def test_native_ytdlp_download_with_mock_network(monkeypatch, tmp_path, audio_file):
    """Real yt-dlp HTTP downloader, local audio response, no external network."""
    import yt_dlp
    import videomind.download_worker as module

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", lambda self, url, download: metadata())
    seen = []
    data = audio_file.read_bytes()
    class Opener:
        def open(self, request, timeout):
            seen.append(request.full_url)
            return addinfourl(io.BytesIO(data), {"Content-Length": str(len(data)), "Content-Type": "audio/webm"}, STREAM, 200)
    monkeypatch.setattr(module, "build_public_opener", lambda jar: Opener())
    result = run_download({"url": URL, "destination": str(tmp_path),
        "limits": {"max_bytes": len(data) + 1, "socket_timeout": 1, "max_duration": 3600}})
    assert result["ok"] is True and seen == [STREAM]
    assert (tmp_path / "source.audio").read_bytes() == data
    assert STREAM not in (tmp_path / "metadata.json").read_text()


@pytest.mark.parametrize("overrides,code", [({"vcodec": "h264"}, "audio_unavailable"),
    ({"protocol": "m3u8_native"}, "audio_unavailable"), ({"filesize": 999999}, "source_too_large"),
    ({"url": "https://evil.test/audio"}, "unsafe_destination")])
def test_download_guard_before_native_download(monkeypatch, tmp_path, overrides, code):
    import yt_dlp
    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", lambda *a, **k: metadata(**overrides))
    def forbidden(*args):
        pytest.fail("Must not start download for rejected metadata")
    monkeypatch.setattr(yt_dlp.YoutubeDL, "process_info", forbidden)
    with pytest.raises(IngestionError) as error:
        run_download({"url": URL, "destination": str(tmp_path),
            "limits": {"max_bytes": 1000, "socket_timeout": 1, "max_duration": 3600}})
    assert error.value.code == code


def test_unknown_size_download_aborted_when_hook_exceeds_limit(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", lambda *a, **k: metadata())
    def download(self, info):
        self.params["progress_hooks"][0]({"downloaded_bytes": 1001})
    monkeypatch.setattr(yt_dlp.YoutubeDL, "process_info", download)
    with pytest.raises(IngestionError) as error:
        run_download({"url": URL, "destination": str(tmp_path),
            "limits": {"max_bytes": 1000, "socket_timeout": 1, "max_duration": 3600}})
    assert error.value.code == "source_too_large"


def test_cli_youtube_needs_authorization(tmp_path, capsys):
    assert main(["--youtube-url", URL, "--output-dir", str(tmp_path / "run")]) == 1
    assert "--authorized" in capsys.readouterr().err
    assert not (tmp_path / "run").exists()
