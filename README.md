# VideoMind AI

Turn an authorized YouTube video or local audio file into a raw transcript and technical study notes, with Word and text downloads. Speech recognition and rewriting run locally with Faster-Whisper and Ollama.

**Status:** working local, single-user application. Generated notes are drafts requiring factual review; software checks do not establish educational accuracy.

## What works

- Responsive Next.js interface with YouTube input and direct audio uploads.
- Background processing, progress, cancellation and reopenable local jobs.
- Transcript/document previews; DOCX, notes TXT and transcript TXT downloads.
- FFmpeg normalization, bounded ASR chunks and versioned transcript stitching.
- Direct transcript-to-notes rewriting with attribution and separate correction/exclusion audits.
- Raw transcripts, timestamps, model calls/settings and source hashes preserved separately from writing outputs.
- Optional second-checkpoint audio verification through the CLI/API, off by default.

```text
YouTube URL / audio upload
  → FFmpeg → bounded audio chunks → Faster-Whisper → raw transcript
  → direct Ollama rewrite → technical notes → DOCX / TXT
```

Rewriting uses one installed Ollama model across bounded transcript chunks. It does not run separate extraction, outline or LLM review passes. Contextual completions are editorial additions, not recovered speech or independently verified facts. The older pipeline remains available through `--pipeline legacy`.

## Getting started

Follow the [fresh-install guide](docs/SETUP.md) for prerequisites, Python/frontend installation and explicit model downloads. A clone does not contain the developer's virtual environment, media, models or generated documents.

Once setup is complete, run from the repository root:

```bash
env -u PYTHONPATH .venv/bin/python scripts/start_local.py
```

| Service | Local URL |
|---|---|
| Application | http://127.0.0.1:3000 |
| FastAPI interactive docs | http://127.0.0.1:8000/docs |
| Backend health | http://127.0.0.1:8000/api/v1/health |

Keep the launcher's terminal open; Ctrl+C stops its frontend/backend processes. Start Ollama separately. Launcher defaults are cached Faster-Whisper `small` and installed Ollama `qwen2.5-coder:7b`.

In the app, paste a single-video YouTube URL or select an audio file, confirm permission, and submit. If YouTube access fails, use an authorized audio upload. Preview the transcript and notes, then download the outputs. No GitHub token or cloud AI API key is needed to run the application.

## Checks and automation

```bash
env -u PYTHONPATH .venv/bin/python -m pytest
cd frontend
npm test
npm run build
npm run typecheck
```

Build before standalone type checking on a fresh clone: Next.js generates route types during the build. See [testing instructions](docs/TESTING.md) for browser integration and optional real-ASR checks.

The [GitHub Actions workflow](.github/workflows/checks.yml) defines backend tests, frontend tests, a production build/type check and Chromium browser integration on pushes and pull requests. Tests use controlled ASR/writer responses, with no YouTube or model downloads. Dependency and Chromium installation require network access. Green checks establish software behavior, not factual accuracy.

## Repository layout

```text
backend/videomind/   FastAPI, CLI, jobs and injectable processing services
frontend/           Next.js, fixed-route loopback proxy and browser tests
tests/              Backend tests and isolated browser-test fixtures
scripts/            Local launcher and synthetic audio fixture generator
docs/               Setup, testing, CLI and legacy workflow guides
.github/workflows/  Automated software checks
```

Local `storage/`, `runs/`, `.cache/`, `.venv/`, frontend dependencies and environment secrets are ignored by Git. Never commit user media, model weights, credentials or generated outputs.

## Limits and remaining work

- ASR can misrecognize terminology, numbers and speech boundaries. Audio-only processing cannot recover diagrams or equations only shown on screen.
- Rewriting can omit details or add incorrect explanations. Selected Python editorial rules are separately audited; general external fact verification and content-quality acceptance remain open.
- The guarded downloader cannot access every YouTube video. It does not bypass restrictions or import browser credentials.
- Long CPU jobs can be slow. Cancellation is cooperative during inference; arbitrary crash recovery/resume, storage quotas and automatic retention are not implemented.
- Services are for a trusted local user on loopback. Authentication, multi-user isolation and public hosting are not implemented. GitHub stores the source; it does not run the application.

See [known issues](ISSUES.md), [quality review](DOCUMENT_QUALITY_REVIEW.md) and [direct-rewrite acceptance](DIRECT_REWRITE_ACCEPTANCE.md). Review technical claims before publishing or teaching from generated notes.

## Documentation

- [Setup](docs/SETUP.md), [testing](docs/TESTING.md), [CLI commands](docs/CLI.md), [legacy pipeline](docs/LEGACY_PIPELINE.md)
- [Architecture](ARCHITECTURE.md), [API](API_DESIGN.md), [requirements](REQUIREMENTS.md), [roadmap](DEVELOPMENT_PLAN.md)
- [Contribution instructions](AGENTS.md), [frontend integration evidence](FRONTEND_INTEGRATION_REPORT.md)

Milestone and acceptance reports are historical evidence. Their `runs/` and `storage/` paths refer to private local artifacts, not files shipped in a clone. Current behavior is described above and in the setup/API guides.
