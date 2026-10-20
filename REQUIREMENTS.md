# Requirements and acceptance criteria

## M1: implemented target

- Ubuntu, Python 3.10+, FFmpeg and ffprobe on PATH; CPU/int8 default, configurable Faster-Whisper model/device/precision/language.
- Accept an existing local media file through a CLI. Validate audio presence and finite duration, normalize to mono 16 kHz PCM on disk.
- Default 300-second cores with 2-second context on each side; validate finite settings and complete, ordered coverage.
- Consume one chunk at a time; retain timestamped raw ASR JSON for every completed chunk and export stitched UTF-8 TXT/JSON.
- Stitch with bounded, timestamp-constrained one-to-one overlap alignment, preserving genuine repetitions and rejecting missing/reordered chunk results. Record unmatched/conflicting candidates and ambiguity. Avoid midpoint-only loss/duplication. Preserve old runs under recorded legacy rules; rebuild only in a new directory. Never invent speech or claim stitching is independent verification.
- Record progress/failure to a manifest, bounded inference retries, refuse overwriting an existing run. Configuration comes from environment plus explicit CLI arguments; no credentials in code.
- Unit tests use mock ASR and generated local WAVs. FFmpeg integration tests verify real media boundaries and failures. An opt-in smoke test runs a real Faster-Whisper model on local speech before any YouTube testing.

M1 acceptance: tests pass; a real local speech file is chunked and transcribed with recognizable expected speech, outputs saved and manifest complete. Mock tests alone do not establish actual ASR works.

## M2 ingestion — implemented scope

- Strict single-video YouTube validation and canonicalization; no arbitrary URLs, playlists or live streams.
- Retrieve sanitized title, channel, duration, license, upload date and source URL using yt-dlp. Require user confirmation of processing authorization; never equate public access with permission.
- Download only accessible direct audio-only HTTPS streams through a guarded transport, with byte/duration/deadline limits. No imported browser cookies, netrc, login, geo-bypass, plugins or remote JS components. Safely fail with upload fallback guidance.
- Keep local-file CLI behavior; add a YouTube CLI mode and an upload/URL FastAPI job endpoint. Both feed the existing M1 transcription service and preserve raw/unverified labels.
- SQLite persistence, atomic job claims, one locked local worker, nonblocking job submission/status, cooperative cancellation, recovery of interrupted runs and UUID-bound TXT/JSON downloads.
- Bound multipart bodies before parsing, check actual media rather than trusting filenames/MIME, reject playlist demuxers, enforce advertised and decoded duration. Restrict browser origins and Host headers for local use.
- Tests: mocked metadata/network failures, real yt-dlp native downloader with mock audio, URL/SSRF rules, upload limits and traversal, state/recovery/queue/cancellation, plus real local speech through the upload API. Live YouTube downloading still requires a user-authorized sample for acceptance testing.

The current user request scopes M2 to ingestion and integration. The dedicated Next.js UI from the original wider roadmap is deferred explicitly; `/docs` is the available interactive submission interface.

## M3 selective audio verification — implemented

M3 selective audio verification is now implemented: separate checkpoint, no primary-text prompt, suspicious section selection, audio-based comparisons with timing checks, bounded wider-context rechecks, uncertainty flags and independent result artifacts. Original raw files remain byte-identical. The standalone CLI and opt-in API route expose evidence and coverage. This is not a correctness certification; default ASR checkpoints share a family and unselected audio remains unchecked. See `MILESTONE_3_REPORT.md`.

Post-review regression gate: preserve case-sensitive scientific symbols, superscripts/subscripts, leading decimals, mathematical punctuation and function brackets. `mW`/`MW` and `10³`/`103` must be flagged as disagreements. Repeated boundary words must be aligned one-to-one, including when timestamp drift would cause both versions to be kept or discarded by the legacy midpoint rule. Tests must also preserve genuine repetition, record conflicts, retain unknown/unchecked boundary uncertainty, validate legacy runs and demonstrate non-destructive reconstruction. See `FIXES_M1_M3.md` and the remaining issues in `ISSUES.md`.

## Technical education document policy

The user requires final documents to use a formal, precise, highly technical educational style. Exclude teacher salutations, social pleasantries, channel promotions and closing chatter. Preserve definitions, equations/units, mechanisms, assumptions, relevant examples, limitations, attribution and uncertainty. Do not discard scientific qualifications or technical examples just because they contain greeting words. Distinguish source claims from independently established facts.

Implemented preparation after verification: separate `document_source.json`/`.txt` outputs conservatively remove clear English chatter and bounded greeting prefixes, retain an exclusion audit with source text/character ranges/word indices/audio times, and preserve uncertainty annotations. Raw and reviewed transcripts are unchanged. Ambiguous, quoted/example-context or disputed content remains for later editorial review. These are preparation artifacts, not independently written documents or fact-checked material. M4/M5 now consume this separate copy for semantic extraction, technical writing, content-integrity review and DOCX.

## Subsequent work (not implemented)

- Next.js/React/Tailwind main page: URL/upload, output choice (verified transcript/document/both), style (technical/academic/educational), status/progress, transcript preview and downloads.
- Distributed task queues/PostgreSQL migration, resumable retries, total storage quota and automatic retention. Local FastAPI/SQLite/worker and ingestion are implemented as described above.
- Further verification work: a distinct ASR family, human adjudication, and representative long/noisy/multilingual accuracy benchmarks. Selective second-checkpoint audio verification and unresolved-span reporting are implemented.

## Operational limits

The application is for a trusted single local user. M2 adds a bounded upload API with a 256 MiB/four-hour default per-source limit; the original direct-file CLI remains available. Disk requirements scale with source duration (~115 MB/hour normalized PCM plus metadata, source copies, temporary multipart spooling and model cache). There is no total retained-storage quota. Five-minute chunks still require ASR model memory. Recognition/timestamp errors remain possible; raw outputs are never labeled audio-verified. Synthetic-speech acceptance proves integration, not production accuracy. Current YouTube access can depend on bot/challenge/runtime requirements, and the conservative downloader may reject otherwise accessible videos. GPU accuracy/performance and public/multi-user deployment are not tested or supported here.

## M4/M5 — implemented local writing and export

- Injectable local Ollama schema-based extraction, thematic outline and concept-based technical writing. Exact quote/ID validation; bounded processing of long transcripts without silently discarding oversized inputs.
- Structured knowledge inventory with concepts, prerequisites, caveats and source/timestamp evidence; writer receives concepts rather than the transcript.
- Separate claim/paragraph source-consistency review and concept-level scientific plausibility risk screen, numeric/measurement-notation heuristics, unchecked/uncertain audio disclosure, omitted-passage coverage and excessive wording overlap flags. External scientific fact verification is not implemented; source agreement cannot establish scientific truth.
- Separate immutable-source outputs with per-file SHA-256 audit, model name/digest/settings and every request/raw response, including schema/model failure evidence. No final Word artifact on failed integrity/structural checks.
- Styled DOCX with title, headings, source attribution, inline evidence references, timestamp table, page numbers, review flags and limitations; independently written TXT/JSON also retained. Flagged Word files are drafts requiring educator review, not certified final facts.
- Standalone document CLI accepts a completed raw or reviewed run. Opt-in API write_document jobs include verification before writing; Ollama failure preserves transcript/report downloads.
- Controlled tests cover hallucinations, unsupported IDs/quotes, measurement case/exponents, copying, truncation, missing review, source preservation/tampering, budgets, cancellation, real DOCX package structure and integrated upload/job/download behavior.
