# Next.js / FastAPI integration — 2026-10-20

The responsive frontend is implemented, connected to FastAPI, built for production, and running locally. The known software regressions exercised below pass. This is not a claim that every possible ASR/LLM factual error has been eliminated.

## Running URLs

- Application: http://127.0.0.1:3000
- Backend API documentation: http://127.0.0.1:8000/docs
- Backend health: http://127.0.0.1:8000/api/v1/health
- Completed real-video example: http://127.0.0.1:3000/?job=cdf50a90-4eea-4447-b507-0d404fab2739

The normal servers were started together with `env -u PYTHONPATH .venv/bin/python scripts/start_local.py`. That launcher defaults to cached Faster-Whisper `small`, local-only model loading, and installed Ollama `qwen2.5-coder:7b`. It binds to loopback, refuses occupied ports, and stops only its own server groups on Ctrl+C. Ollama was already running locally. No system Node upgrade or system service was installed.

## Implemented interface

The app has a responsive desktop workspace and mobile layout; validated single-video YouTube input; an authorized-audio upload fallback; queue/stage/percentage progress; cancellation; early raw-transcript preview while writing continues; structured document preview with code formatting; DOCX, notes TXT and original-transcript TXT downloads; actionable API/download/connection errors; reconnecting status polling; recent browser history; refresh recovery and `?job=UUID` links.

Media/model text is rendered as text, not injected HTML. Study notes are labeled AI-generated drafts. No secondary audio-verification pass runs unless explicitly requested outside this normal UI flow. The interface does not claim scientific certification.

A Next.js server-side proxy forwards only fixed health/job/artifact routes to a configured loopback FastAPI origin. It validates loopback Host and same-origin requests, including the localhost/127.0.0.1 distinction, streams uploads with a byte limit, refuses redirects, preserves download bytes and filenames, and sanitizes connection errors. Backend TrustedHost/origin controls were not relaxed. The frontend uses local assets/system fonts, not remote fonts.

## Failures fixed before acceptance

- The model repeated the known global-name-uniqueness/type-conversion errors after a retry. Selected reference-backed editorial rules now correct these exact regressions, and restore the explicitly taught `pass` keyword when omitted. Every edit and its reference is stored separately in `rewrite_audit.json`; original model responses and all transcripts remain unchanged. See the Python [name-binding reference](https://docs.python.org/3.13/reference/executionmodel.html#binding-of-names), [numeric-type reference](https://docs.python.org/3.13/library/stdtypes.html#numeric-types-int-float-complex), and [pass reference](https://docs.python.org/3.13/reference/simple_stmts.html#the-pass-statement). These narrow rules are not a general factual-verification system.
- Next.js internally identified a 127.0.0.1 browser request as localhost, incorrectly rejecting valid submissions. The proxy now compares against the actual validated loopback Host, without trusting forwarded host headers. Cross-origin writes and non-loopback reads remain blocked.
- Primary ASR and writer callbacks used `completed` before the job itself finished. Distinct `transcription_completed` and `document_completed` stages now prevent a premature “notes ready” label.
- Completed raw transcripts were inaccessible during writing. The API now advertises/serves them only after the primary manifest records completed evidence, even if writing is pending or later fails.
- Preview reload now clears stale job state before fetching; downloads use an attached temporary anchor; small-text contrast and mobile controls were improved after screenshot inspection.

## Executed checks

| Check | Result |
| --- | --- |
| `env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q` | **357 passed**, 32.59 seconds, including the three cached real-ASR smoke tests |
| `cd frontend && npm test` | **5 passed**, actual named tests with normal Node subprocess support |
| `npm run typecheck` | Passed |
| `npm run build` | Production build passed |
| `npm run test:e2e` | **7 Chromium tests passed**, 32.9 seconds |
| `npm audit --omit=dev --audit-level=high` | 0 reported vulnerabilities at the check |
| Real YouTube → real ASR → local Ollama → browser previews/downloads | Passed; details below |

The browser suite starts separate FastAPI/Next servers on ports 8001/3100 with controlled offline ASR/writer dependencies. It exercises actual HTTP multipart upload, worker/storage/FFmpeg orchestration and document rendering through the real Next proxy. It covers successful YouTube submission/progress/previews/download bytes, refresh/deep-link recovery, URL/permission validation, unavailable video, writing failure with preserved transcript, mobile overflow, cancellation, cross-origin rejection, outage/reconnect behavior and a successful upload whose HTML-like filename remains literal text. Fixtures are isolated in `tests/ui_fixture_server.py` and never enabled by the production app factory.

The first sandbox build/test attempts could not spawn Node subprocesses; file-level Node summaries from those attempts were not counted. The build and actual five named unit tests were rerun successfully with normal subprocess support. FastAPI socket tests and browser tests likewise ran with normal local sockets. Initial integration failures were fixed and the entire browser suite rerun successfully.

## Real production test

Video: https://www.youtube.com/watch?v=fWjsdhR3z3c (Indently, approximately 10½ minutes).

The job was submitted through the browser form with authorization, downloaded through the guarded production downloader, transcribed using the cached `small` model, and rewritten with **two live Qwen writing calls**. The completed document has 11 sections and three audited selected-reference edits. The taught `pass` keyword is present, the known uniqueness/dynamic-conversion phrases are absent, Word ZIP/readability checks pass, and source-integrity checks confirm the raw artifacts stayed unchanged.

Browser results: desktop/mobile layouts fit, document and original transcript previews loaded, DOCX and both TXT downloads completed, refresh recovery succeeded, and no browser runtime errors were recorded. The browser test initially stopped after submission because its harness lacked a request base URL; the same already-running job was resumed rather than submitting a duplicate download/ASR job.

Artifacts:

- `runs/frontend-live-test-03/report.json`, screenshots and downloaded DOCX/TXT snapshots.
- `runs/frontend-final-check-01/report.json` and final desktop/mobile screenshots.
- `storage/jobs/cdf50a90-4eea-4447-b507-0d404fab2739/` holds the production job, original evidence, model calls, source integrity and rewrite audit.
- `runs/fwjsdhr3z3c-test-01/document-integrity-02/` is the separate pre-UI real-lecture regression check. Earlier failed/diagnostic runs remain unchanged.

## Files and operating notes

Frontend: `frontend/app/`, `frontend/lib/`, pinned `package.json`/`package-lock.json`, `next.config.ts`, unit tests, Playwright config/browser tests, and opt-in `scripts/live-check.mjs`. Startup: `scripts/start_local.py`. Backend changes: `api.py`, `worker.py`, the direct writer and new `services/rewrite_integrity_service.py`; backend regression tests include `test_frontend_api.py` and `test_rewrite_integrity.py`. README, API design, example environment and contributor instructions describe the current implementation.

Current Next.js requires Node >=20.9 ([official installation guide](https://nextjs.org/docs/app/getting-started/installation)); the project pins a local Node 24 runtime and npm scripts use that binary. Route handlers follow the current [Next.js route API](https://nextjs.org/docs/app/api-reference/file-conventions/route). Application ports remain 3000/8000; test servers are shut down after the suite.

These services are local, single-user tools. Interrupted backend inference is not automatically resumed; a browser refresh does not stop a running backend job. The known targeted regressions and tested software paths pass, but audio recognition, important-topic coverage and other generated claims can still be wrong. Historical lecture drafts are intentionally not overwritten. There is no basis for calling all AI-generated educational content error-free; educator review remains necessary before publication or teaching.
