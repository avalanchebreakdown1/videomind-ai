# VideoMind AI

The default workflow is **audio/authorized YouTube → FFmpeg → Faster-Whisper → raw transcript → direct Ollama rewrite → Word document**. Audio verification is optional and off by default. Transcripts and historical runs remain unchanged. A responsive Next.js frontend is available at `http://127.0.0.1:3000` when started locally.


## Run the local application

The Next.js interface provides YouTube input, an audio-upload fallback, real job progress, transcript and study-note previews, DOCX/notes TXT/transcript TXT downloads, cancellation, recent browser history, and reopenable `?job=UUID` links. Audio verification stays off by default. Files and original transcripts remain on this computer; notes remain generated drafts requiring review.

Install and build the frontend once (dependencies are pinned in `frontend/package-lock.json`):

```bash
cd frontend
npm ci
npm run build
cd ..
```

The frontend includes a project-local Node 24 runtime; npm scripts use it instead of modifying the system Node installation. Cached Faster-Whisper `small` and installed Ollama `qwen2.5-coder:7b` are the local launcher's defaults. Start your local Ollama server first if it is not already running; the app never downloads Ollama models automatically.

```bash
env -u PYTHONPATH .venv/bin/python scripts/start_local.py
```

- App: `http://127.0.0.1:3000`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

Ctrl+C in the launcher's terminal stops both of its own server process groups. The launcher refuses occupied ports. Model settings may be overridden with the existing `VIDEOMIND_*` variables. The frontend's server-only `VIDEOMIND_API_URL` defaults to `http://127.0.0.1:8000`; no permissive CORS configuration is needed. Do not expose these local single-user services publicly.

Checks:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q
cd frontend
npm test
npm run typecheck
npm run build
PLAYWRIGHT_BROWSERS_PATH="$PWD/../.cache/ms-playwright" node_modules/node/bin/node node_modules/@playwright/test/cli.js install chromium
PLAYWRIGHT_BROWSERS_PATH="$PWD/../.cache/ms-playwright" npm run test:e2e
```

Browser tests start isolated FastAPI/Next servers on ports 8001/3100 with controlled offline ASR/writer dependencies; production uses ports 8000/3000 and real models. The real-video browser test is opt-in: `VIDEOMIND_LIVE_URL` must be explicitly supplied to `frontend/scripts/live-check.mjs`. See `FRONTEND_INTEGRATION_REPORT.md` for executed results and limitations.

## Direct transcript rewrite (default)

Use an already installed Ollama model. This command processes the existing full lecture transcript without repeating transcription or verification:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document \
  --source-dir runs/m1-m4-test-01/transcription \
  --output-dir runs/m1-m4-test-01/my-direct-document-01 \
  --model llama3.1:8b \
  --source-title 'Python Programming Fundamentals' \
  --source-url 'https://www.youtube.com/watch?v=CtbckFw0pJs'
```

Every attempt requires a new output directory. One model pass rewrites each bounded transcript chunk with preceding and following context. The default is 6,000 characters per direct chunk (`VIDEOMIND_WRITE_DIRECT_CHUNK_CHARS`). No concept extraction, outline generation, separate LLM review or content gate runs on this path. One schema retry is permitted. The instructions retain technical explanations, examples, equations and qualifications; remove chatter; and use subject context to repair recognisable transcription errors. Unrecoverable fragments should be omitted rather than filled with fabricated details. Code checks allow reconstructed local names, spoken number words and explanatory comments, while excluding unsupported calls, imports and literals with an audit. Source instructions and URLs are never executed or fetched.

The Word document has headings, formatted code and attribution, with no inline uncertainty markers. Contextual completions are editorial additions, not recovered speech or independently checked facts. `rewrite_audit.json` records model-reported corrections, excluded code and chunk processing; it cannot guarantee that the model disclosed every change. No external factual verification is performed.

Outputs: `document.docx`, `document.txt`, structured `document.json` / `reading_document.json`, the unfiltered `candidate_document.json`, `source_chunks.json`, `rewrite_audit.json`, `quality.json`, `manifest.json`, `integrity.json`, and raw model requests/responses. Deterministic reading cleanup removes clear greetings, classroom boilerplate and orphaned example labels with an audit. Source hashes are checked before delivery. Every source character is submitted; complete retention of technical details still needs human evaluation. Failure preserves diagnostics and withdraws final reading artifacts.

Full-lecture processing succeeded, but review still found factual errors and omissions with both installed models. The current workflow is **not content-quality accepted**. See [DIRECT_REWRITE_ACCEPTANCE.md](DIRECT_REWRITE_ACCEPTANCE.md) for the actual runs, latest reading copy, code execution checks, and remaining failures. This test reused the complete existing transcript; it did not repeat YouTube ingestion or ASR.

The CLI returns **2 when it produces an unreviewed direct-rewrite document**; this is not a processing failure. It returns 1 for failure, 130 for interruption. The previous pipeline is available explicitly with `--pipeline legacy`; saved knowledge/model-call reuse requires that mode.

For the API, submit `write_document=true` with an authorized file or YouTube URL. Leave `verify=false` (the default). Download `/api/v1/jobs/{id}/document`, with `?format=json`, `txt`, `quality`, `rewrite-audit` or `source-chunks`. Knowledge/evidence/content-gate reports apply only to historical legacy jobs and return 404 when absent.

## Historical extraction/review pipeline (`--pipeline legacy`)

Install project dependencies with `.venv/bin/python -m pip install -e '.[dev]'`. Start your local Ollama server and select an installed model with `ollama list`. The default is `llama3.1:8b`; the application never downloads Ollama models automatically.

The following section documents the previous pipeline, available only with `--pipeline legacy`. Its evidence-linked reviews and inline warnings do not apply to the default direct rewrite.

For an existing completed verification run:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document --pipeline legacy \
  --source-dir runs/ctbckfw0pjs-verify-fixed-smoke-01 \
  --output-dir runs/ctbckfw0pjs-document-01 \
  --model llama3.1:8b \
  --source-title 'Technical lecture' \
  --source-url 'https://www.youtube.com/watch?v=CtbckFw0pJs'
```

Use a new output directory for each attempt. This hour-long source has only 90 seconds of audio review so far; the document will disclose uncertain/unchecked evidence. A completed raw transcription directory is also accepted, with all cited audio marked unchecked. No audio is downloaded or re-transcribed by this command. Source title/creator/URL can be supplied for attribution; URLs are stored as text and never fetched. YouTube metadata is used automatically when adjacent to the source run.

If extraction completed but writing failed, reuse its saved knowledge rather than repeating extraction:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document --pipeline legacy \
  --source-dir runs/m1-m4-test-01/verification \
  --reuse-knowledge runs/m1-m4-test-01/document-03 \
  --output-dir runs/m1-m4-test-01/document-new-attempt \
  --model llama3.1:8b \
  --source-title 'Educational video test' \
  --source-url 'https://www.youtube.com/watch?v=CtbckFw0pJs'
```

`--reuse-knowledge` names a prior document run containing completed extraction, not the verification directory. Reuse validates current source hashes, prepared passages, every saved successful extraction request/response and the reconstructed knowledge; altered or incomplete artifacts are rejected before model work. The old run stays immutable, and the new run records reuse provenance/hashes. This skips extraction only; writing and review run afresh. Writing and claim review now update progress and save explicitly incomplete checkpoints.

When a later run has already written/reviewed part of the document, optionally add `--reuse-model-calls PATH_TO_THAT_RUN`. Saved calls are reused only when source hashes/passages, recorded model digest and the complete outgoing request match. Responses are parsed and checked again by current code. Changed prompts/settings use new inference; replayed calls keep their raw responses and source hashes in `model_reuse.json`. Reuse never edits the old run, and consumes the current call budget. Saved replay inputs are limited to 20 MB per artifact and 128 MB total.

If a reviewer returns several assessments for the same requested item, all reasons and original assessments are preserved. The combined result uses the most cautious verdict (`unsupported` before `uncertain` before `supported`; factual `needs_review` before `no_obvious_issue`). Assessments for unknown/wrong items still fail. This handling does not silently discard contradictory evidence.

Outline assembly validates all known concept IDs, removes duplicate references, and restores omitted concepts under their saved topic headings, recording these decisions in `outline.json`. Unknown concept IDs still fail. This preserves concept coverage without asking the model to invent replacement content; it does not certify factual correctness or resolve poor source recognition.

The writer sees extracted concepts rather than the transcript, builds a thematic outline and synthesizes an explanation. Exact source quotes and timestamps support concept citations; separate Ollama passes assess source consistency for every concept/paragraph and scientific plausibility risks for every concept. Ollama selects evidence IDs from a batch-specific schema; the application copies the selected source passages verbatim, so the model cannot alter citation text. One bounded retry is allowed for invalid reference-selection fields; attempts are preserved in `model_calls/` and `extraction_validation.json`. References still undergo separate source-support review. Concept granularity is allocated across all batches from the configured concept/call budgets and recorded in `knowledge.json`; unrepresented passages remain explicit review findings. Extraction progress updates after each batch. Unsupported/uncertain claims, potential scientific errors in the source, altered numeric values or measurement notation, omitted source coverage, unchecked audio and excessive wording overlap produce **visible review flags in Word**. These checks can miss errors: source consistency is not external scientific fact verification. Documents remain AI-generated drafts requiring an educator's review. Failed integrity/schema checks prevent final DOCX delivery and retain failure evidence.

Outputs include `document.docx`, `document.txt`, `document.json`, `knowledge.json`, `evidence.json`, `quality.json`, `prepared_source.json`, a source SHA-256 integrity audit, manifest, and every model request/raw response. Source files are hashed before and after processing; neither raw nor reviewed transcripts are rewritten. Clear salutations/channel chatter are excluded from the prepared copy with an audit; technical examples and uncertainties stay recoverable.

CLI exit codes: **0** source-consistency checks passed (not fact verification), **2** document produced but needs review, **1** processing failure, **130** interrupted. A reviewable draft is not a failed download.

For a new API upload/YouTube job, add `write_document=true` in `/docs` or multipart form data. Audio verification is skipped by default, including document jobs. Add `verify=true` only when you explicitly want the optional second audio pass. Without it, writing uses the completed raw transcription directly; the source remains marked as unchecked. Retrieve `/api/v1/jobs/{id}/document` for Word, or `?format=quality`, `knowledge`, `evidence`, `json`, `txt`. Ollama work runs in the background worker. Raw and reviewed transcripts remain downloadable if writing fails. No website/UI has been added.

Writing settings use `VIDEOMIND_WRITE_` followed by: `MODEL`, `ENDPOINT` (default `http://127.0.0.1:11434`, HTTP loopback IP only), `TIMEOUT_SECONDS` (180 per request), `RUN_TIMEOUT_SECONDS` (3600 for model processing), `CHUNK_CHARS` (3500), `MAX_CHUNKS` (80), `MAX_CALLS` (512), `MAX_CONCEPTS` (160), `NUM_CTX` (8192), `NUM_PREDICT` (2200). Requests are non-streaming, schema-constrained and deterministic in settings, but hardware/model nondeterminism remains possible. Finite limits fail explicitly; no silent truncation or automatic retry hides missing evidence. Long lectures may take many minutes and can exceed budgets. Cancellation is checked between model requests, with an active request limited by its timeout. Ollama must run locally; its own configuration determines any server-side behavior. Prompt and response artifacts contain source text; treat them as private project data.

See `MILESTONE_4_5_REPORT.md` for executed checks and remaining limitations.

## Legacy content quality: candidate versus reading copy

Processing completion does **not** establish document quality. The first full-lecture draft contained genuine errors: reversed language-level explanations, garbled ASR terminology, invented elaborations, classroom conversation and verification metadata presented as lesson content. See `DOCUMENT_QUALITY_REVIEW.md`; content-quality acceptance remains open.

New runs retain the full generated candidate in `document.json`. After source/factual-risk review, a content gate withholds paragraphs with blocking findings, failed/missing dependent assessments or pipeline metadata leakage. Remaining candidates receive a topic-aware editorial screen for substantive technical relevance. The exported DOCX/TXT and normal API JSON preview use `reading_document.json`; `content_gate.json` retains withheld paragraphs, reasons and citation-marker edits. Withheld content is not silently replaced by guessed corrections. An empty or partial reading copy is clearly labeled; it must not be presented as a complete lecture reconstruction. Source uncertainty can still require review, and false-negative/false-positive model judgments remain possible.

Word shows review counts rather than reproducing the faulty candidate as an educational explanation or filling the appendix with its unsupported wording. `quality.json`, `document.json` and the content-gate audit retain the diagnostic detail. API `?format=content-gate` exposes the audit; legacy jobs without a reading copy retain their historical JSON behavior.

A separately edited, reference-checked Python guide is available at `runs/m1-m4-test-01/document-reference-corrected-04/document.docx`. It uses 13 official sources and four executed examples. It is a scoped editorial correction, **not** automatic recovery of every word/topic in the lecture and not evidence that the Ollama pipeline now performs authoritative external fact verification.

## Verify an existing transcript using audio

Your completed YouTube run can be reviewed without downloading or transcribing the primary audio again:

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind verify \
  --run-dir 'runs/ctbckfw0pjs-test-01~/transcription' \
  --output-dir runs/ctbckfw0pjs-verification-01 \
  --model small
```

The `small` model is cached in this workspace. For a fresh setup, omit `VIDEOMIND_LOCAL_FILES_ONLY=true` on first use to allow downloading the verifier weights. The source must be a completed M1/M2 transcription directory containing its original raw artifacts and `normalized.wav`; verification writes to a **new, separate directory outside it**. The `~` in the example is part of your existing folder name. Each attempt needs a new output directory.

Verification selects suspicious regions using primary word probabilities, segment metrics, repeated words/phrases, gaps, chunk boundaries and recorded stitching uncertainty, plus start/middle/end audits. It decodes up to 30-second core sections with context through a separate Faster-Whisper instance/checkpoint. Comparison now preserves scientific case, superscripts/subscripts, leading decimals, primes, factorials and brackets using NFC rather than compatibility folding. Only a trailing full stop/comma on plain alphabetic words of at least three letters is ignored. Harmless capitalization/formatting differences can therefore be flagged conservatively. Meaning-changing examples such as `mW`/`MW` and `10³`/`103` cannot be supported as equal. Reports identify `scientific_nfc_case_sensitive_v2`; older reports lacking this marker used the previous rules and should be regenerated before relying on their scientific-token support. A disagreement or low secondary confidence can trigger one wider-context recheck. The second ASR receives audio and a language hint, never a primary-text prompt.

Agreement is evidence, not proof. Both default models belong to the Whisper family and may share errors. No candidate is automatically substituted into the primary transcript: disagreements remain uncertain even if repeated secondary passes agree or a recheck later returns the original wording. No LLM or synonym rewriting is involved.

| Verification artifact | Contents |
|---|---|
| `verification.json` | Selection reasons, audio intervals, all ASR candidates/comparisons, rechecks/errors, checkpoint fingerprints, source hashes, coverage and counts |
| `verified_transcript.json` | Original text plus word-level `supported_by_second_asr`, `uncertain` or `not_checked` statuses and separate `annotated_text` |
| `verified_transcript.txt` | Original wording with `[uncertain: ...]` markers and unresolved audio-section notes |
| `sections/000000/pass1.json`, `pass2.json` | Original second-model segments, absolute words, crop boundaries and comparison evidence |
| `manifest.json` | Separate review progress/state and provenance |

The stage hashes original TXT, JSON, chunk evidence, manifest, versioned stitching/rebuild evidence when present, and normalized audio to check preservation; it never writes into the primary run. Temporary review WAVs are removed after use. Peak decoded audio is bounded by section plus context (default up to 42 seconds on recheck). Coverage is measured over core intervals, excluding duplicate context. `audio_verification_performed` means at least one section produced ASR evidence; `all_audio_checked` describes time coverage. Known but unreviewed stitching ambiguity stays uncertain, with per-word `audio_reviewed` distinguishing checked and unchecked words. The global `audio_verified` remains false. Empty candidates do not prove silence.

## Boundary stitching fix and existing runs

New transcriptions use `overlap_alignment_v2`: one-to-one, order-preserving word alignment inside shared audio, constrained by at most one second of midpoint drift. Matching occurrences are emitted once without independently discarding both versions at a core boundary. Real repeated words in both candidates remain distinct. Words recognized in one candidate only are retained; conflicting hypotheses for the same time are alternatives rather than concatenated speech. `stitching.json` preserves boundary candidates/decisions and flags single-word ambiguity, conflicts, drift and missing shared context. Unresolvable cases still need audio review. Alignment has a bounded token-matrix budget and fails explicitly instead of exhausting memory.

Your original transcript is unchanged. A separate rebuilt run using its saved original ASR chunks is available at `runs/ctbckfw0pjs-restitch-fixed-01/`. It required no YouTube access, new primary ASR or model download. It preserves exact copies of chunk evidence and normalized audio, with original-source hashes in `restitching.json`.

To rebuild another old run into a **new** directory:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind restitch \
  --run-dir 'runs/ctbckfw0pjs-test-01~/transcription' \
  --output-dir runs/my-rebuilt-transcript
```

You can then run `videomind verify --run-dir runs/my-rebuilt-transcript --output-dir runs/my-new-review --model small`. Rebuilding is not independent audio verification. Older runs without a stitching marker remain readable under the original `midpoint_v1` rules; no historical files are silently rewritten. See [FIXES_M1_M3.md](FIXES_M1_M3.md) for reproduced defects, final validation and [ISSUES.md](ISSUES.md) for remaining work before advancing.

Defaults are in `.env.example`: 0.65 probability threshold, 30-second sections, 2-second initial/6-second recheck context, 1-second timing tolerance, 8-second gap trigger, at most 200 sections. These are heuristic thresholds, not calibrated accuracy probabilities. `--max-sections 3` is useful for a short smoke test. The report explicitly counts omitted candidate sections and unchecked words; a limited run must not be described as full-video verification. Original transcripts remain accessible if verification fails. CLI exit codes: 0 for a finished review (which can still contain uncertainty), 2 when some selected sections failed, 1 for setup/input errors, 130 for interruption.

For new API jobs, submit **`verify=true`** alongside your usual source and authorization. The worker transcribes first, then verifies before finishing. Fetch `/api/v1/jobs/JOB_ID/transcript?kind=verified` or `/api/v1/jobs/JOB_ID/verification`; default `kind=raw` continues to return the unchanged raw output. Previously completed API jobs are not requeued or mutated; use the CLI on their transcription directory to add review separately. See [MILESTONE_3_REPORT.md](MILESTONE_3_REPORT.md).

## Technical document preparation

New verification runs also create `document_source.json` and `document_source.txt` for the later technical-writing stage. This separate copy excludes clear English greetings such as “Hello friends, how are you?”, channel welcomes, like/subscribe requests and closing chatter. A bounded greeting prefix can be removed while preserving the technical introduction that follows. Each exclusion records its original text, character range, word indices, audio times and reason.

This cleanup preserves technical definitions, equations, units, assumptions, examples and limitations. Quoted/programming examples, ambiguous language and disputed speech are retained for editorial review. Uncertain retained words keep their statuses and `[uncertain: ...]` annotations in the TXT export. Raw and audio-reviewed transcripts are never edited by cleanup. The JSON includes the required formal technical writing policy and `fact_checked: false`; this is source preparation, not a guarantee that a speaker's claims are facts. Full semantic selection, original technical writing, attribution/factual review and Word export remain later milestones.

For API jobs requesting verification, use `GET /api/v1/jobs/JOB_ID/document-source` for the preparation JSON or `?format=txt` for its annotated text attachment. Existing review artifacts are not rewritten automatically; generating a new review also generates the preparation outputs.

## YouTube ingestion

```bash
env -u PYTHONPATH .venv/bin/python -m videomind \
  --youtube-url 'https://www.youtube.com/watch?v=VIDEO_ID' \
  --authorized --output-dir runs/my-youtube-run --model tiny.en --language en
```

Replace `VIDEO_ID` with the video's 11-character ID. `--authorized` confirms you have permission to process it; public accessibility alone does not establish permission. The service validates/canonicalizes the URL, retrieves metadata with yt-dlp, downloads an accessible direct audio-only stream, checks the actual media, then transcribes it. It does not import browser cookies, log in, use netrc credentials, spoof geography, or bypass access controls. Restricted, age-gated, live, unavailable, oversized and unsupported-format videos fail with an upload fallback message.

Watch, youtu.be, shorts and embed links are accepted; playlists, credentials, explicit ports, fragments and arbitrary hosts are rejected. Tracking parameters are discarded. Network requests and redirects use allowlisted HTTPS hosts, validated public DNS addresses pinned to the connection, and certificate verification. The downloader runs as a bounded child process; no shell commands or user-supplied downloader options are accepted. No plugins or remote JavaScript components are loaded. Some current YouTube streams require runtime/challenge support this conservative configuration does not provide, so uploads remain the fallback. The user completed a live YouTube transcription of video `CtbckFw0pJs`: 13 chunks, 3767.23 seconds. That establishes this video's ingestion/transcription path, not access to every YouTube source or word-perfect recognition.

YouTube CLI output: `ingestion.json`, sanitized `download/metadata.json`, `download/source.audio`, and the normal M1 artifacts under `transcription/`. Signed stream URLs and raw extractor responses are not persisted. Existing local-file CLI syntax and output paths are preserved.

## Local upload and background-job API

```bash
env -u PYTHONPATH VIDEOMIND_MODEL=tiny.en VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m uvicorn videomind.api:create_app --factory \
  --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/docs** for the interactive API form. Submit `POST /api/v1/jobs` with `authorized=true` and **either** `youtube_url` **or** an audio file. This is the backend's interactive API documentation; a dedicated Next.js website is not included in this ingestion milestone.

For a direct upload from a terminal:

```bash
curl -F 'authorized=true' -F 'file=@samples/generated/speech.wav' \
  http://127.0.0.1:8000/api/v1/jobs
```

The response is `202 Accepted`, with an ID and Location header. Poll `GET /api/v1/jobs/JOB_ID` for metadata, stage, progress and safe errors. Fetch `GET /api/v1/jobs/JOB_ID/transcript` for JSON preview, or append `?format=txt` to download TXT. `POST /api/v1/jobs/JOB_ID/cancel` cancels a queued job immediately or requests running-job cancellation. An API request does not wait for ASR.

One worker owns `storage/worker.lock`; use one API process without `--workers` or `--reload`. SQLite and per-job files live in `storage/`. Queued jobs survive restart; interrupted running jobs become failed (or cancelled if requested). Retries are new submissions. Cancellation is cooperative between pipeline steps/chunks; YouTube downloads can be killed promptly. An active inference or FFmpeg operation must finish or reach its timeout before acknowledging cancellation. Do not remove job storage while the worker is running.

Defaults: 256 MiB/source, four hours/media, 15-minute download deadline, 20-second socket timeout, and five queued/running jobs. Export the limits in `.env.example` to change them. Request bodies, including chunked transfers, are bounded before multipart parsing. Filenames are generated; client filenames never become storage paths. Known media containers are accepted, and playlist/concat demuxers are rejected. Normalization enforces the duration cap on decoded output as well as the advertised duration. Per-request spooling temporarily uses additional disk. Completed storage has no automatic retention or total disk quota yet.

The API is for a trusted local user only: bind to loopback. Browser requests from unrelated origins and untrusted Host headers are rejected. Authentication, multi-user isolation, distributed workers and public deployment are outside this milestone. See [API_DESIGN.md](API_DESIGN.md) and [MILESTONE_2_REPORT.md](MILESTONE_2_REPORT.md).

## Setup

Requires Python 3.10+ and `ffmpeg` / `ffprobe`. This workspace already has Python 3.10.12 and FFmpeg 4.4.2 on Ubuntu 22.04.5. A project virtual environment and downloaded `tiny.en` test model are available. No system packages were changed.

For a fresh environment:

```bash
python3 -m venv .venv
env -u PYTHONPATH .venv/bin/python -m pip install -e '.[dev]'
```

The environment inspected for this project inherits ROS directories through `PYTHONPATH`. Clearing that variable for project commands prevents unrelated ROS pytest plugins and dependencies from leaking into the virtual environment. It does not alter the shell or ROS installation.

`requirements.lock` records the exact dependency versions tested on Ubuntu/Python 3.10. To reproduce them in a fresh virtual environment, install `-r requirements.lock` before installing this project. `pyproject.toml` declares the supported dependency ranges.

## Transcribe a local file

```bash
env -u PYTHONPATH .venv/bin/python -m videomind /path/to/audio.mp3 \
  --output-dir runs/my-first-transcription --model base --language en
```

The output directory must be new. Model names download weights on first use and need network access. Subsequent use can be offline with `VIDEOMIND_LOCAL_FILES_ONLY=true`. Model cache defaults to `.cache/models` relative to the current directory. Run commands from the repository root, or set an absolute `VIDEOMIND_MODEL_DIR`. `--model` also accepts a local converted Faster-Whisper model directory. Default `base` balances local test cost and quality; use representative audio to evaluate your own model choice. The downloaded smoke-test model is `tiny.en`, not `base`.

Defaults: CPU, int8, 4 CPU threads, automatic language detection, 300-second core chunks, 2 seconds of context on each side, one retry after an ASR exception. Use `--chunk-seconds`, `--overlap-seconds`, `--keep-chunks`, or exported variables listed in [.env.example](.env.example). The application does not automatically read `.env`. CPU is the tested path; CUDA is not configured or tested. Adapter integration follows the [Faster-Whisper documentation](https://github.com/SYSTRAN/faster-whisper).

## Outputs

| Path within run | Meaning |
|---|---|
| `raw_transcript.txt` | UTF-8 assembled speech output, without a generated explanation |
| `raw_transcript.json` | Same text plus absolute word times and model probabilities |
| `raw_chunks/000000.json` | Original segments, relative timestamps and absolute words for each chunk |
| `chunks.json` | Ordered core and overlap intervals |
| `manifest.json` | Settings, status, monotonic progress, warnings, errors and available outputs |
| `normalized.wav` | Mono 16 kHz PCM retained for future audio review |
| `audio_chunks/` | Empty by default after processing; retain copies with `--keep-chunks` |

The CLI reports progress on stderr and the final TXT path on stdout. Exit code 0 means processing completed, 1 indicates failure, 130 indicates Ctrl-C. Empty recognition completes with an explicit warning. Failures preserve completed chunk evidence and a failed manifest. Choose a new output directory to retry; resumable jobs and background processing are future milestones.

FFmpeg writes normalized media to disk. ASR decodes only one bounded chunk at a time. Budget roughly 115 MB/hour of normalized audio, plus source media, model weights and optional retained chunks. Transcript metadata grows with word count. There is no storage quota in this trusted local CLI.

## Tests

Unit and FFmpeg/API integration suite (mock ASR and mock YouTube responses; no model or YouTube downloads):

```bash
env -u PYTHONPATH .venv/bin/python -m pytest
```

In the Codex network sandbox, FastAPI TestClient's cross-thread event-loop wakeup hangs before application startup. Run the suite in the normal local environment, or grant the test command sandbox escalation. There is no need to modify ROS, the network configuration or application timeouts.

Create your own locally synthesized speech fixture using the FFmpeg flite filter installed on this Ubuntu system:

```bash
.venv/bin/python scripts/create_sample.py
```

The generator refuses to overwrite an existing fixture. The sample and expected speech already exist under `samples/generated/` in this workspace. On systems lacking flite, supply an authorized local speech WAV and set `VIDEOMIND_TEST_AUDIO`.

Download the small smoke-test model once (network required):

```bash
env -u PYTHONPATH .venv/bin/python -c "from faster_whisper.utils import download_model; download_model('tiny.en', cache_dir='.cache/models')"
```

Run the real ASR test; it requires cached weights and makes no model-download requests:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -m real_asr -s
```

The real CLI test uses two overlapping chunks, checks recognizable beginning/middle/end content, retains the repeated phrase “solar panels”, and verifies completion and the raw/unverified label. A second real test exercises direct upload, background processing and transcript download through FastAPI. A third real test reviews source audio using the distinct cached `small` checkpoint and asserts source preservation and evidence/coverage. It requires `runs/smoke-final` and the cached verifier weights; default tests remain offline and use controlled ASR disagreements. For a persistent CLI output folder set `VIDEOMIND_TEST_OUTPUT=runs/a-new-smoke-run`. Milestone 1 artifacts remain under `runs/smoke` and `runs/smoke-final`. Reports: [M1](MILESTONE_1_REPORT.md), [M2](MILESTONE_2_REPORT.md), [M3](MILESTONE_3_REPORT.md).

## Accuracy and project scope

Overlap alignment replaces the original midpoint-only method, which could duplicate or discard a word when chunk timestamps straddled a boundary. Original chunk outputs and boundary alternatives remain available. Single-word/repetition ambiguity, drift beyond the matching tolerance and ASR omissions still require audio review; text/timestamps alone cannot determine the actual speech in every case. Stitching is not independent verification. Synthetic speech validates integration, not accuracy on long, noisy, multilingual or multi-speaker recordings. An empty result does not prove silence. Never use language models to invent missing speech.

Only process media you are authorized to use. Future educational writing will separate source concepts, new structure, attribution and quality review. Rewriting does not automatically remove copyright obligations.

Project design: [ARCHITECTURE.md](ARCHITECTURE.md), [REQUIREMENTS.md](REQUIREMENTS.md), [API_DESIGN.md](API_DESIGN.md), [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), [AGENTS.md](AGENTS.md).
