# Architecture

## Scope and boundaries

VideoMind AI is a local-first modular monolith. M1 implemented the local CLI. M2 added a YouTube CLI and local FastAPI upload/job API, SQLite and a single background worker. M3 adds selective audio verification with a separate checkpoint and separate uncertainty/evidence artifacts. M4/M5 now implement local Ollama knowledge extraction, technical writing, source-consistency review and Word export. The Next.js UI remains planned.

Implemented flow:

```
local file -> ffprobe -> FFmpeg mono 16 kHz PCM on disk
           -> bounded overlapping WAV chunks -> Faster-Whisper
           -> immutable per-chunk raw JSON -> bounded overlap alignment + boundary evidence
           -> raw_transcript.txt + raw_transcript.json + manifest.json
```

FFmpeg normalization streams to disk, not a Python audio buffer. Each five-minute core has up to two seconds of context on either side. Only one chunk is decoded by ASR at a time. The ASR model is loaded once. Chunk WAVs are removed after use unless explicitly retained. Normalized PCM remains for future audio review. Disk use grows with source duration; chunk audio memory is bounded, transcript metadata grows with word count.

Words retain absolute source times. New runs use versioned `overlap_alignment_v2`: monotonic one-to-one matching within shared audio with at most one second midpoint drift. This fixes deterministic duplication/loss caused by independently assigning shifted versions to chunk cores. Genuine matched repetitions remain one-to-one. Single-candidate words are retained; overlapping incompatible hypotheses select one source sequence and retain both as explicit alternatives. Shared context edges, single-word matches, timing reconciliation and conflicts are flagged for audio review in `stitching.json` and raw JSON. A 100,000-cell alignment budget prevents unbounded matrix allocation. Ambiguous speech is not claimed resolved by text matching. Historical runs use recorded versions, defaulting to `midpoint_v1`; an explicit rebuild creates a new run without changing the original.

## Application boundary

Planned Next.js/React/Tailwind -> implemented FastAPI -> SQLite job repository -> local worker -> services -> artifact directory. Bind local services to loopback. APIs enqueue work and return promptly; inference never runs in request handlers. One CPU worker owns an OS lock. Repository methods and worker orchestration are separate from audio services so PostgreSQL and Celery/Redis can replace persistence/scheduling later. Dedicated UI construction is deferred from this ingestion scope.

YouTube: strict parser -> isolated download child -> sanitized metadata/access/duration gate -> yt-dlp native direct HTTPS audio downloader -> existing media pipeline. A custom transport guards metadata and media requests, including redirects, with allowlisted hosts and pinned public DNS results. TLS validation stays enabled; proxies, plugin loading, persisted/browser cookies, netrc, geo-bypass and remote JS components are not used. Public access does not prove legal authorization: the CLI/API requires user confirmation. Signed stream URLs never leave the download process. A parent deadline and cancellation polling bound the child lifetime.

Uploads: bounded whole multipart request spooled before parsing -> bounded file copy into generated job directory -> queued SQLite row -> worker probes and normalizes media. Multipart spooling is disk-bounded per request, not a global storage quota. Known container demuxers are allowlisted to prevent uploaded playlists from referring to other files. Source and decoded duration are bounded for API/YouTube jobs. Existing trusted local-file CLI use remains uncapped unless explicitly configured by its caller.

Required service ownership:

| Module | Responsibility | Status |
|---|---|---|
| youtube_service.py | Strict URL parsing, isolated yt-dlp retrieval, size/time limits | Implemented M2 |
| network_service.py | Allowlisted HTTPS, redirect checks and public-IP pinning | Implemented M2 |
| ingestion_service.py | YouTube CLI orchestration and ingestion failure manifest | Implemented M2 |
| audio_service.py | Probe and normalize local audio, restricted FFmpeg protocols | Implemented M1 |
| chunking_service.py | Ordered overlapping chunk plan and on-demand extraction | Implemented M1 |
| transcription_service.py | Lazy Faster-Whisper adapter, timestamped primary ASR | Implemented M1 |
| stitching_service.py | Versioned, bounded overlap alignment; repetition preservation, conflict/ambiguity evidence; legacy reader | Implemented M1, fixed after M3 review |
| text_service.py | Case-sensitive NFC comparison preserving scientific notation | Implemented M3 fix |
| restitching_service.py | New-run reconstruction from original chunk outputs with preservation audit | Implemented M1/M3 fix |
| verification_service.py | Selective second-model audio ASR, disagreement spans, bounded rechecks, evidence/uncertainty, immutable source hashes | Implemented M3 |
| content_service.py | Conservative, auditable chatter exclusion in a separate technical-writing source; preserves uncertainty/examples | Implemented M3 follow-up |
| understanding_service.py | Concept inventory with exact quotes, stable IDs, prerequisites and caveats | Implemented M4 |
| rewriting_service.py | Thematic outline and concept-based explanation; writer sees no original quotes/transcript | Implemented M4 |
| quality_service.py | Separate source-consistency and scientific-risk reviews, numeric/unit heuristics, uncertainty/coverage/similarity flags | Implemented M4; not external fact verification |
| ollama_service.py | Loopback HTTP, strict JSON schemas, bounded contexts/calls/time/responses, model digest and request/response audit | Implemented M4 |
| writing_pipeline.py | Immutable-source orchestration, attribution, failure manifest and integrity audit | Implemented M4/M5 |
| document_service.py | Atomic TXT/JSON and styled DOCX with citations and visible review flags | Implemented M1/M5 |

Do not add empty modules implying planned services are implemented.

## Artifacts and evidence

Raw transcript is primary ASR output assembled by timestamp, never corrected by a language model. The M3 reviewed derivative is a separate version with audio-based evidence and uncertainty. It preserves original wording and does not automatically replace words. The AI-written document is a third artifact with its own outline, attribution and review report. Rewriting does not eliminate copyright obligations.

M3 uses a separately configured Faster-Whisper model instance/checkpoint consuming source audio, without primary text prompts. Same aliases and identical available model weights are rejected. Whisper-family checkpoints may still make correlated errors; a distinct model-family adapter is future work. The primary checkpoint fingerprint for older M1/M2 runs reflects currently available cache/path weights, because those original manifests did not pin a model revision at inference time.

Selection bins low-probability words, poor metrics, repetitions, gaps, boundaries and recorded stitching issues into bounded cores, plus start/middle/end audits. A budget prioritizes suspicious regions; omissions remain explicit. Token comparisons preserve letter case and use NFC, not NFKC, retaining SI-symbol case, exponents/subscripts, leading decimals, primes, factorials and brackets. Harmless prose capitalization may overflag; no semantic equivalence is inferred. New reports record comparison/source-stitching versions. Low confidence or edit/timing disagreement can trigger one wider-context recheck. Contradictory evidence stays uncertain. Known unchecked assembly issues retain uncertainty, source candidates and `audio_reviewed: false`; text-only review never counts as audio verification.

`verification.json`, `verified_transcript.{json,txt}`, per-pass evidence and a separate progress manifest are written outside the original transcription directory. Every original transcript/chunk/manifest and normalized-audio hash is checked for preservation. Temporary review WAVs are removed. `audio_verification_performed` records successful ASR evidence, `coverage_fraction`/`all_audio_checked` record time coverage, and no global correctness claim is made. The original transcript stays downloadable if verification setup fails. Both-empty candidates remain uncertain; missing primary speech is represented as uncertain audio spans, not inserted text.

## Reliability and safety

M1 records `created -> normalizing -> transcribing -> stitching -> completed`, with failure from any nonterminal state. Atomic manifest updates include monotonic progress, completed chunk count and error details. Outputs live in a new run directory; existing directories are rejected. ASR exceptions get bounded retries; malformed input fails without retries. No resumability or cancellation in M1; interruption records failure. A failure never publishes completion.

M2 persists jobs in SQLite with private generated job directories, atomic claims, monotonic progress and immutable terminal states. Interrupted running jobs fail on restart; queued jobs remain available. Cancellation is cooperative between chunks/stages, with prompt termination during the download subprocess. ASR and FFmpeg steps are not forcibly interrupted by cancellation. Retries create new jobs. Artifact routes derive fixed filenames from UUID job IDs and require completed jobs. Raw pipeline evidence stays on disk; signed URLs and internal error details are excluded from API responses. Dedicated artifact-table checksums and retention are deferred. The single-process lock prevents worker conflicts; distributed execution is not supported.

API defenses include whole-request size limits, generated storage paths, explicit source authorization, Host validation and local browser-Origin checks. It has no authentication or multi-user authorization and must remain on loopback. Restricted/inaccessible videos produce safe errors and an upload fallback. A live, user-authorized YouTube download is still a manual acceptance check; default tests use mock external responses.
