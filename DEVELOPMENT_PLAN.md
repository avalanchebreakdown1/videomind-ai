# Implementation roadmap

Current user authorization includes M4/M5 knowledge extraction, original writing and DOCX after the comparison/stitching fixes. Remaining M1–M3 limitations stay tracked and are not implicitly closed. See `FIXES_M1_M3.md` and `ISSUES.md`. Original runs/reports stay immutable; any reconstruction or re-verification uses new output directories.

## Milestone 1 — local audio transcription

1. Inspect environment and create design/requirements/API/contributor documentation.
2. Implement typed configuration, streamed normalization, bounded chunks, injectable Faster-Whisper adapter, ordering/stitching, raw evidence and atomic TXT/JSON export.
3. Test planning, real extraction, repeated words/boundaries, ordering, retries, failure transitions and artifact integrity with mock ASR.
4. Run real ASR on a local synthetic speech fixture, forcing multiple chunks; inspect recognizable text, coverage and manifest. Record reproducible commands/results in `MILESTONE_1_REPORT.md`.

Gate: do not start Milestone 2 until the local pipeline works. Stop after M1 and report evidence and limitations.

## Milestone 2 — ingestion, jobs and web interface

Current user-scoped ingestion implementation: strict YouTube validation and guarded yt-dlp ingestion, bounded direct uploads, SQLite repository/local worker, FastAPI API, cancellation, recovery and transcript download routes. Tests cover URLs/SSRF, native downloading with mocked network, state transitions, nonblocking submissions, cancellation/failure, and local speech uploaded through the real ASR pipeline. See `MILESTONE_2_REPORT.md` for final evidence and remaining limits.

Deferred from the original wider M2 roadmap: the dedicated Next.js/React/Tailwind website. Interactive API submission is available at `/docs`. After the M2 report, the user successfully ran a live YouTube download/transcription of `CtbckFw0pJs` through all 13 chunks. That source's completed run is available for M3 audio-review checks. M3 was then explicitly authorized; UI and document writing remain deferred.

## Milestone 3 — independent audio verification

Implemented: separate configurable ASR checkpoint over selected audio sections, suspicious-region planning, timestamp-aware candidate comparison, bounded wider-context rechecks, explicit uncertainty, raw-artifact hash preservation and separate persisted results. Standalone CLI reviews existing runs; opt-in API jobs add a verifying stage and report/download routes. Controlled-disagreement tests and real second-model audio checks are recorded in `MILESTONE_3_REPORT.md`. A second model family, human adjudication UI and full-length accuracy benchmarking remain future work. Stop after reporting M3; do not start writing or export milestones without a new request.

## Milestone 4 — educational writing and review (implemented)

Ollama adapter with bounded contexts/timeouts; concept inventory with evidence, original thematic outline, independent writing, explicit attribution. Quality service flags unsupported facts, close source similarity and absent attribution; revision cannot silently remove unresolved issues. Tests use fixed AI responses and adversarial source text.

User clarification: final documents must be formal, highly technical educational explanations without greetings, social chatter, channel promotion or casual narration. Preserve technical examples, assumptions, equations, limitations, attribution and uncertainty. M3 now supplies an auditable, conservatively filtered document-source copy; M4 must perform semantic content selection and factual review before writing. Source claims are not automatically established facts. Do not merely paraphrase the transcript sentence by sentence.

## Milestone 5 — exports and complete integration (local document scope implemented)

Professional DOCX styles/metadata/attribution and TXT export for selected output modes. End-to-end tests from authorized source/upload through verification, writing, review and downloads. Document setup, privacy, limits and accuracy evaluation. Add quotas and deployment controls before anything beyond local use.
