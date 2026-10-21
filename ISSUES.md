# Known issues and historical milestone findings

## Current workflow status

The Next.js frontend, FastAPI integration, direct Ollama rewrite and DOCX/TXT export are implemented. Audio verification is opt-in and off by default. Current setup/tests are in [README](README.md) and [the testing guide](docs/TESTING.md).

Remaining priorities are human-reference ASR/content accuracy evaluation, resumable jobs/hard inference timeouts, storage/resource quotas and broader authorized-source testing. Direct writing can omit or distort technical details; selected reference-backed Python repairs do not establish general factual correctness. Software tests and completed browser runs do not close content-quality acceptance.

## Historical M1–M3 tracking

The entries below retain earlier milestone findings. Later authorization added writing and UI without implicitly closing those accuracy/reliability limits. User instruction during that pass: address existing-milestone issues before advancing. No M4/M5 or UI implementation was started during the fixes below. This tracker distinguishes reproduced defects from accuracy limits and later-stage features; passing tests is not a blanket correctness claim.

## Reproduced defects fixed in 0.3.1

| ID | Defect | Closure evidence |
|---|---|---|
| D1 | Casefold/NFKC and broad punctuation stripping falsely supported scientific changes, including `mW`/`MW`, `10³`/`103`, `.5`/`5`, and function brackets | NFC/case-sensitive, notation-preserving comparison; regression matrix covers SI case, chemical notation, powers/subscripts, decimals, primes, factorials, punctuation, brackets and Unicode canonical equivalence |
| D2 | Independent midpoint ownership could duplicate or discard both timestamp-shifted versions of one boundary word | Versioned, bounded one-to-one overlap alignment; both reproduced cases pass; genuine repetitions preserved; conflicting/limited candidates explicitly flagged; old runs validate under legacy rules and can be rebuilt separately |

See `FIXES_M1_M3.md` for exact tests, preservation audits and actual-video rebuild/review results. D2 closes the deterministic assembly defect, not the inherent ambiguity of arbitrary ASR hypotheses: unresolved words still need audio evidence/human review.

## Remaining M1–M3 quality and reliability work

| ID | Status | Work needed |
|---|---|---|
| R1 | Open: real-source accuracy acceptance | Finish reviewing the hour-long recording and inspect representative technical terms, numbers, negation, omissions and all flagged boundaries against audio. The initial fixed-version smoke covered 90 seconds; the subsequent user run in runs/m1-m4-test-01/verification reports 100% audio coverage, 126 uncertain sections and zero processing failures. Human-reference accuracy evaluation remains incomplete. Use a human reference to measure accuracy; do not interpret flagged words as proven incorrect or supported words as guaranteed correct. |
| R2 | Open: correlated recognition errors | Both available checkpoints share Whisper ancestry. A different ASR family or human adjudication is needed for stronger corroboration. Separate checkpoint passes do not establish mathematical independence. |
| R3 | Open: long-job recovery/resource controls | Hard ASR watchdog, resumable chunk/review processing, total retained-storage quota, concurrent upload-spool budget and earlier capacity admission remain absent. Cancellation is cooperative during inference; local single-user limits still apply. |
| R4 | Evaluation needed: ingestion variability | Test more authorized formats/videos and access/network failures under representative conditions. JS/challenge-dependent or restricted streams can fail; uploads remain the fallback. Do not bypass restrictions to improve coverage. |
| R5 | Open: preparation quality | Conservative English rules do not provide complete semantic relevance filtering; test varied lectures and audit exclusions. Technical examples/qualifications and disputed material must stay recoverable. Full semantic selection belongs to the writing stage, not audio accuracy verification. |
| R6 | Open: inference provenance | Old primary manifests did not pin the exact loaded checkpoint revision at inference time; current-cache fingerprints cannot retroactively prove it. Future primary runs should record resolved model/version fingerprints during inference. Preserve historical uncertainty instead of inventing provenance. |

These are not all closed by D1/D2. The user has now explicitly authorized M4/M5 implementation. These M1–M3 issues remain open; that authorization does not establish accuracy acceptance or close the reliability work.

## Boundaries for later stages

- Scientific truth checking is separate from faithfully recognizing speech. Current preparation outputs explicitly set `fact_checked: false`; M4 must implement grounding/attribution/factual review.
- Diagrams, equations shown without speech and demonstrations are not recovered by audio-only processing. Visual extraction would be additional scope, not an implicit ability of M1–M3.
- The service remains loopback/single-user only. Authentication, multi-user isolation and public hosting are not implemented.
- Local Ollama writing, DOCX and the Next.js frontend are implemented. General external scientific fact verification and dedicated human adjudication tooling remain future work. See FRONTEND_INTEGRATION_REPORT.md and DIRECT_REWRITE_ACCEPTANCE.md.

## Legacy M4/M5 quality findings

The extraction/outline/review details below describe `--pipeline legacy`. Default writing is now direct rewriting and does not run these review/content-gate passes. Historical failures are retained as evidence, not claims about current pipeline stages.

**Content-quality acceptance failed on the user's lecture draft.** See `DOCUMENT_QUALITY_REVIEW.md`. A working pipeline and 317 passing integration/regression tests did not establish a reliable educational document. The new reading-copy gate withholds flagged text, and a separately edited official-reference-backed Python guide is supplied; general automatic factual grounding and recognition correction remain open.

- Local Ollama source-consistency and separate scientific plausibility screens can both miss mistakes; using the same model does not provide independent factual corroboration. Source-faithful claims are not automatically true. Publication/teaching requires educator review and authoritative references where needed.
- Lexical similarity and numeric/unit checks are conservative heuristics, not exhaustive semantic, mathematical or plagiarism checks. Unicode notation is retained as text, not Word equation objects. Visually presented material remains absent.
- No automatic correction/revision loop is allowed to hide unresolved claims. Flagged documents are explicitly drafts. The quality report is evidence for review, not an acceptance certificate.
- Long inputs may exceed concept/call/context/deadline budgets and fail with retained evidence rather than silently truncate. There is no resume; use a new output directory/job. Prompt injection defenses reduce risk but do not prove model robustness.
- Scientific accuracy and long-lecture educational completeness have not been benchmarked. A full hour-long lecture writing recovery has now completed with all 77 concepts represented, but its 344 overlapping review findings require human adjudication; processing success is not content-quality acceptance. See MILESTONE_4_5_REPORT.md.

Writing recovery follow-up: the original global-outline membership check could abort after completed extraction when Ollama omitted known concepts. Application-side outline assembly now restores known omissions with an audit and rejects unknown IDs. The CLI can reuse validated extraction from a prior writing run and replay exact matching saved model calls with source/model provenance. Writing/quality state is recomputed from the responses; incomplete checkpoints are diagnostic, not blindly accepted. Arbitrary crash-resume and distributed recovery remain absent. Multiple reviews for one requested item are combined conservatively with original assessments retained; unknown-item assessments remain errors.
