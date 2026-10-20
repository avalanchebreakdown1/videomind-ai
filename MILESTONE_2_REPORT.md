# Milestone 2 — ingestion report

Date: 2026-10-19 (Asia/Tokyo). Implemented the ingestion scope requested in this turn and tested it as detailed below. The dedicated Next.js UI from the original broader roadmap is explicitly deferred. No independent-verification or document-writing milestone was started.

## Implemented

- YouTube CLI mode using strict single-video URL validation, canonical video IDs, yt-dlp metadata extraction and native direct audio-only downloading.
- Explicit user confirmation of authorization. Public accessibility is not proof of permission. No credentials, netrc, browser-cookie imports, geo-bypass, plugin loading or remote JS components. Restricted, live, unfinished, unknown-duration and unsupported audio sources are rejected.
- HTTPS transport used for both metadata and media: host allowlist, redirect checks, public-IP validation and pinning at connection time, original hostname TLS verification, and disabled proxies. Private, loopback, link-local, reserved and multicast destinations are rejected.
- Download isolation in a child process, bounded socket/retry settings, total deadline, byte limits and partial-file cleanup. Sanitized title/channel/license/date/source/duration metadata is retained; signed stream URLs and raw extractor errors are not persisted or exposed by the API.
- Direct audio uploads through FastAPI as a fallback. The whole multipart body is bounded before parser spooling, including chunked requests. File bytes are counted again during copying. Generated per-job filenames prevent client-path traversal. Actual audio is probed; MIME/extension alone is never trusted. Playlist/concat demuxers are rejected. Duration limits apply before and during normalization.
- SQLite jobs and one local background worker: prompt 202 submission, status/progress, atomic claims, bounded queue, recovery of interrupted jobs, cooperative cancellation and immutable terminal states. An OS file lock prevents conflicting API workers.
- Both sources feed the existing M1 pipeline. Raw TXT/JSON preview/download endpoints are available only after completion. The existing local-file CLI syntax, outputs and tests are preserved.
- Structured safe request/worker errors with actionable upload fallback. New submission is the retry mechanism.

API endpoints: `POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs/{id}/transcript`, `POST /api/v1/jobs/{id}/cancel`. The document endpoint explicitly returns 409 because writing is not implemented. Interactive submission is available via FastAPI `/docs`.

## Files created or updated

Created:

- `backend/videomind/{api,repository,worker,ingestion_config,download_worker}.py`
- `backend/videomind/services/{youtube_service,network_service,ingestion_service}.py`
- `tests/test_youtube.py`, `tests/test_jobs_api.py`, and this report.

Updated:

- `cli.py`: YouTube arguments; original local-file mode preserved.
- `pipeline.py`, `audio_service.py`, service package description: optional bounded normalization and restricted media demuxers.
- `tests/test_audio_pipeline.py`: playlist and duration-limit regression coverage.
- `pyproject.toml`, `requirements.lock`, `.env.example`, `.gitignore`: dependencies, tested snapshot, configurable ingestion limits, storage exclusions; package version 0.2.0.
- `README.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, `API_DESIGN.md`, `DEVELOPMENT_PLAN.md`, `AGENTS.md`: current implementation, setup, security boundaries, deferred UI and next steps.

Installed dependencies only in the project `.venv`; no system-wide configuration was changed. Existing M1 reports and run artifacts remain intact.

## Tests executed and results

| Check | Result |
|---|---|
| `env -u PYTHONPATH .venv/bin/python -m pytest` | **166 passed**, 2 opt-in ASR tests deselected; final run 5.63 seconds, no warnings |
| `env -u PYTHONPATH VIDEOMIND_TEST_API_STORAGE=runs/milestone2-api-smoke .venv/bin/python -m pytest -m real_asr -s` | **2 passed**, 166 deselected; 3.32 seconds, no warnings |
| Editable install for package 0.2.0 | Passed |
| `env -u PYTHONPATH .venv/bin/python -m pip check` | No broken requirements found |
| CLI `--help` | Passed; both source modes and authorization flag present |

Default tests use mock ASR, mock YouTube metadata and mock network audio responses. They make no external YouTube/model download requests. Crucially, one test uses **the real yt-dlp native HTTP downloader and our guarded URL-opening adapter** with a locally supplied audio response; only extraction metadata and the network response are mocked. Other tests cover process result handling, child timeout/cancellation, partial cleanup, byte limits including unknown sizes, access failures, rejected protocols and destinations, pinned DNS/TLS host behavior, URL spoofing and playlists, upload size/body limits, traversal attempts, duration rejection, corrupt media, queue saturation, restart recovery, terminal-state immutability, worker ownership and nonblocking API cancellation.

Real ASR checks use the cached `tiny.en` model on CPU/int8 and the locally synthesized M1 speech fixture. The original CLI still passes. The new API check uploads the file, receives 202, polls a real background job, then previews/downloads the transcript. It completed **2/2 chunks** for **14.815 seconds** of speech. A separate word-token comparison found all **38 expected words** in the same order, ignoring punctuation and case. This is a synthetic integration result, not a general accuracy benchmark or independent audio verification.

Persistent API smoke evidence:

```
runs/milestone2-api-smoke/jobs/3db0c7cd-4ce3-47e7-9352-7e4968db68c8/
  source.audio
  transcription/manifest.json
  transcription/raw_transcript.txt
  transcription/raw_transcript.json
  transcription/raw_chunks/000000.json
  transcription/raw_chunks/000001.json
```

SQLite state is retained in `runs/milestone2-api-smoke/jobs.sqlite3`. Artifacts are ignored by version control. The smoke test server is closed; no background server was left running.

The shell inherits ROS Python paths; project commands clear `PYTHONPATH`. Initial FastAPI TestClient attempts hung while waking the event-loop thread, before application startup, under the socket-restricted Codex sandbox. Approved runs outside that sandbox passed. Application network protections were retained. The multipart replay adapter was also adjusted to await the underlying receiver after end-of-body, avoiding an empty-message busy loop.

## How to use

Start the local API with the already cached small model:

```bash
env -u PYTHONPATH VIDEOMIND_MODEL=tiny.en VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m uvicorn videomind.api:create_app --factory \
  --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. Submit an audio file or a YouTube URL with `authorized=true`, poll the returned job Location, and use its transcript endpoint after completion. `README.md` also documents CLI and curl examples.

Default limits: 256 MiB/source, four hours/media, five queued/running jobs, 900-second download deadline and 20-second network socket timeout. Change them through exported environment variables listed in `.env.example`.

## Known limits and pending acceptance

- **No live YouTube download was performed.** No user-authorized video was supplied. External extraction/access is therefore not acceptance-verified; do not infer live success from mocked tests. A user-authorized URL is needed for that check.
- Current YouTube bot checks, runtime requirements, format changes and geographic/access restrictions can prevent downloading. The conservative implementation supports accessible direct HTTPS audio-only streams; it deliberately rejects HLS and does not enable JS runtime/remote challenge components. Use an authorized audio upload when unavailable. Metadata is normally surfaced on the job after download/probing finishes; sanitized metadata is retained on disk if extraction succeeded before a later download failure.
- The dedicated Next.js/React/Tailwind application is **not implemented in this ingestion pass**. `/docs` is the current interactive API interface. No browser UI QA or live HTTP deployment test is claimed; FastAPI integration is tested in-process.
- All outputs remain **raw/unverified**. A second independent ASR pass, AI-written documents, factual/similarity/attribution review and DOCX are future work.
- One local worker/process only. Running inference/FFmpeg cancellation is cooperative between operations; downloads can be killed promptly. No hard ASR watchdog, distributed workers, partial-job resume or automatic retry linking.
- The API is loopback-only in supported use. It has Host/Origin restrictions and bounded ingestion but no authentication or multi-user authorization. Do not expose it publicly.
- Per-source/request limits are enforced; total retained-storage quota, automatic retention and a global concurrent-upload spool budget are not implemented. Completed/failed/cancelled source files and evidence remain until manually managed. Queue limits apply after upload completion.
- Real tests cover short synthetic English speech on CPU, not noisy, multilingual or long-video accuracy/GPU performance. The original five-hour chunk-plan test is planning coverage, not long-duration ASR benchmarking.

## Next step

Review these results. The next acceptance check is a live user-authorized YouTube URL. The dedicated web interface can follow as a separate step. No further milestone work was started.
