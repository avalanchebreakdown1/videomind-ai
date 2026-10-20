# Milestone 3 — selective audio-based verification

Date: 2026-10-19 (Asia/Tokyo). Implemented and tested. No writing, DOCX or UI milestone was started.

## Result

Completed primary transcripts can now be reviewed against selected sections of their retained audio using a separately initialized ASR instance with a distinct checkpoint. The original run is read-only to this stage. Review artifacts go into a new directory outside the primary transcription directory.

Suspicion signals include low primary word probability, poor segment metrics, repetition, untranscribed gaps and chunk boundaries. Start/middle/end audio audit sections also check high-confidence material. Selection is bounded and prioritized, with omitted candidates and unchecked words explicitly recorded.

The verifier receives audio and the source language hint, never a primary-text prompt. Candidate comparison uses word alignment and absolute times, ignoring case/sentence punctuation while preserving numerical signs/decimals/units. Text or timing disagreements and low secondary confidence trigger at most one wider-context audio recheck where additional context exists. Inference exceptions have bounded retries. Identical crop rechecks are skipped.

No candidate is automatically substituted into the source. Matching evidence can support a word; disagreement remains uncertain even if later secondary passes agree with each other or return the original wording. Missing/added candidate speech is represented in the comparison evidence and uncertain audio spans. Empty output from both models does not prove silence. All original wording remains in the reviewed JSON's `text`; annotation is separate.

## Files created

- `backend/videomind/verification_config.py`: validated environment configuration and limits.
- `backend/videomind/services/verification_service.py`: planning, checkpoint identity checks, source validation/hashes, extraction, second ASR/rechecks, comparison and separate artifact export.
- `backend/videomind/verification_cli.py`: standalone `videomind verify` workflow, progress and exit codes.
- `tests/test_verification.py`: controlled candidate disagreements, timing/confidence/numeric cases, preservation, retries, interruption/cancellation, configuration, identity and real ASR.
- `tests/test_verification_api.py`: opt-in API review, report/downloads, same-model rejection, setup failure/raw availability and section-level ASR failures.
- This report.

Updated `cli.py`, `worker.py` and `api.py` to expose CLI dispatch and opt-in `verify=true` API jobs. Existing raw-only behavior remains the default. Updated `.env.example`, package version 0.3.0, README, API/architecture/requirements/roadmap documents and AGENTS instructions. No new Python dependencies or system configuration changes were needed. Downloaded the `small` checkpoint to the project cache with approved network access and reinstalled the local editable package.

## Interfaces and artifacts

Standalone existing-run review:

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind verify \
  --run-dir 'runs/ctbckfw0pjs-test-01~/transcription' \
  --output-dir runs/ctbckfw0pjs-verification-01 \
  --model small
```

Choose a new output directory per attempt. `small` is cached in this workspace; fresh environments need a first-use weight download or a preinstalled local model. A different named checkpoint/available weight fingerprint from the primary is required. Custom local models are accepted; identical weights under different paths are rejected.

For a new API job, add `verify=true` to `POST /api/v1/jobs`. Read the job's `verification` summary, `GET /api/v1/jobs/{id}/verification` for evidence, and `GET /api/v1/jobs/{id}/transcript?kind=verified&format=txt` for an annotated attachment. The default transcript endpoint still serves the original raw output. A verification setup failure does not remove raw transcript access. Completed older jobs are not modified/requeued; their on-disk transcription directory can be reviewed with the standalone CLI.

Separate output files:

| File | Evidence |
|---|---|
| `verification.json` | Selection reasons, crop ranges, candidates/comparisons, rechecks/errors, hashes, settings, checkpoint fingerprints, coverage and counts |
| `verified_transcript.json` | Unchanged original text plus annotated text, per-word statuses and uncertain audio spans |
| `verified_transcript.txt` | Original wording annotated with `[uncertain: ...]`, scope notice and unresolved-section notes |
| `sections/NNNNNN/pass1.json`, optional `pass2.json` | Original second-model outputs and explicit audio/core intervals |
| `sections/NNNNNN/result.json`, optional attempt records | Section outcome and retained failures |
| `manifest.json` | Separate review status/progress and provenance |

Review WAVs are extracted and deleted one pass at a time; audio itself remains available in the untouched primary `normalized.wav`. The report identifies the exact crop needed to reproduce a pass. Defaults: 30-second cores with 2 seconds of initial context per side, 6 seconds per side on recheck, 0.65 word-probability threshold, 1-second timing tolerance, 8-second gap trigger, maximum 200 sections. At most one context recheck is performed. Thresholds are heuristics, not calibrated error probabilities.

Word states: `supported_by_second_asr`, `uncertain`, `not_checked`. `audio_verification_performed` indicates at least one successful audio pass; `coverage_fraction` and `all_audio_checked` describe core time coverage. Global `audio_verified` remains false: neither agreement nor complete time coverage certifies correctness. Section failures finish as `completed_with_errors`, with uncertainty and CLI exit code 2. Setup failures exit 1; interruption exits 130. Exit 0 can still include unresolved disagreements.

## Tests executed

Final complete M1–M3 suite:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -o addopts=''
```

**212 passed in 19.92 seconds, no warnings.** This includes 209 default tests and 3 opt-in real-ASR checks. The command used approved execution outside the socket-restricted sandbox for FastAPI TestClient's local thread/event-loop communication. Default tests do not download models or contact YouTube.

Controlled verification cases cover substitutions, omissions, insertions, low secondary confidence, matching text at incompatible times, numerical signs/decimals, Unicode normalization, secondary-pass instability, wider-context reprocessing, rechecks disabled/no extra context, retries/permanent failures, invalid timestamps, empty recognition, suspicious metrics/repetitions/gaps/boundaries, budget omissions, raw evidence tampering, same-model aliases/copied weights, distinct local models with identical folder names, output collision, interruption and cancellation. API cases confirm raw-vs-reviewed separation and raw availability after verification setup failure. All pre-existing ingestion, upload, queue, cancellation, transcription and stitching tests also pass.

The real verification test reviews the locally synthesized 14.815-second sample using `small` against the original `tiny.en` output. It checks successful audio evidence, full time coverage on this short fixture, more than 20 supported words, distinct checkpoint fingerprints and source preservation. The original real CLI and real upload-to-transcript tests pass too.

Additional checks: editable package 0.3.0 installation passed; `pip check` reports no broken requirements; `videomind verify --help` passed.

## Real YouTube-recording smoke test

Input: the user's already completed 13-chunk run at `runs/ctbckfw0pjs-test-01~/transcription`, duration **3767.228688 seconds**. No new YouTube download or primary retranscription was performed.

Executed:

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind verify \
  --run-dir 'runs/ctbckfw0pjs-test-01~/transcription' \
  --output-dir runs/ctbckfw0pjs-review-smoke-01 \
  --model small --max-sections 3
```

Results:

- Completed without failed sections; exit 0.
- Reviewed three prioritized 30-second cores: **90 seconds / 3767.23 seconds, 2.389% time coverage**. Each received a second, wider-context pass, for six ASR passes total.
- **110 words supported**, **104 uncertain**, **9881 not checked**. An uncertain word is not necessarily wrong; it lacks consistent corroboration under this comparison.
- Three unresolved sections; 123 candidate sections omitted by the explicit three-section smoke-test budget. This is not full-video verification.
- All original TXT/JSON, chunk files, chunk plan and manifest hashes match before/after. The retained normalized-audio hash also matches. A separate post-run audit confirmed preservation. No temporary review WAVs remain.
- Primary `tiny.en` weights SHA-256: `1a5afae06a4db91c975c9a9d78be5cc110ee4ea022ad57d55492e4550e936b2a`.
- Secondary `small` weights SHA-256: `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.
- Cached secondary snapshot: `536b0662742c02347bc0e980a01041f333bce120`.

Inspect `runs/ctbckfw0pjs-review-smoke-01/verification.json` and `verified_transcript.txt`. The broader example command above omits the three-section cap and uses the default 200-section budget. Review its reported coverage and failures after completion rather than assuming every word was verified.

## Known limitations

- This is a separate audio pass with distinct weights, **not a distinct ASR family**. Both default models derive from Whisper and can agree on the same error. A second-family adapter is future work.
- Suspicion heuristics and audit samples cannot catch all confident mistakes. Budgeted runs leave explicit unchecked regions. The full hour-long recording has not been reviewed end-to-end; only the documented 90-second smoke run was executed.
- No human adjudication or automatic corrections. Rechecks strengthen the evidence trail but never erase contradictions. A reviewer must resolve uncertain speech by listening.
- Older M1/M2 manifests did not pin the exact model revision at inference time. Primary fingerprints here identify currently available cache/path weights, not a retroactively proven original revision. Missing weights can leave fingerprints null; model identifiers remain recorded.
- Word timestamps and cross-model tokenization can differ, especially across languages. Timing tolerance and lexical comparison can overflag or miss disagreements. Model confidence is not a calibrated accuracy measure.
- Gap/empty-output checks do not establish silence or detect all omitted speech. Candidate insertions are retained as unresolved audio evidence, never invented into the transcript.
- Selection/model inference remains bounded by sections/context and retry counts, but there is no hard inference watchdog or resume-from-partial-review implementation. Cancellation is cooperative; completed pass evidence and a failed review manifest are preserved on interruption.
- Metadata/evidence memory grows with transcript size, while decoded audio is bounded. CPU/GPU speed and long/noisy/multilingual accuracy have not been benchmarked. Both primary and secondary models can remain resident in the local API worker.
- Verification requires the original normalized audio and internally consistent raw artifacts. It refuses to run against modified/incomplete evidence or overwrite an existing output directory. Public deployment/multi-user isolation remain unsupported.

## Next milestone

M4 concept extraction, original educational writing and quality/attribution review is not started. M5 Word export is also not started. Review the evidence and uncertainty behavior before authorizing subsequent work.

## Follow-up — technical education content preparation

The user clarified that final documents must be highly technical educational material, excluding teacher salutations, social chatter and channel promotion. Implemented a separate editorial source preparation step after audio verification. It does not change the raw or reviewed transcript.

New files: `backend/videomind/services/content_service.py` and `tests/test_content_service.py`. Updated verification export, API artifact listing/downloads, existing verification integration tests and project requirements/design documentation.

New verification runs write `document_source.json` and `document_source.txt`. Clear English greetings, social pleasantries, channel welcomes, like/subscribe requests and closing chatter are excluded from this copy with an audit trail: original text, source character ranges, word indices, audio times and reasons. Bounded greeting prefixes can be removed without dropping a technical introduction. Quoted/programming examples, scientific assumptions/limitations, numerical units, ambiguity and disputed speech remain. Retained uncertainty is visible in annotated TXT and preserved in JSON statuses. The final-writing policy requires precise terminology, independent concept organization, technical examples, attribution and separate factual review.

The API exposes `GET /api/v1/jobs/{id}/document-source?format=json|txt` after a newly completed verification job. Older artifacts are not retroactively changed. The original `/document` endpoint remains unimplemented because independent writing and Word export have not begun.

Final follow-up validation: **230 tests passed in 19.89 seconds**, including 18 focused preparation cases, full existing regression tests, three real-ASR checks and API integration. No warnings. A direct controlled demonstration converted “Hello friends, how are you? Force equals mass times acceleration. Thanks for watching.” into “Force equals mass times acceleration.” and confirmed the original source stayed unchanged.

Limitations: preparation currently uses conservative English rules, not full semantic relevance analysis. Ambiguous, quoted/example-context or uncertain material is deliberately retained for M4 editorial review. Outputs explicitly state `is_final_document: false` and `fact_checked: false`; removing chatter does not validate a speaker's factual claims. Final technical writing, full semantic filtering, factual/attribution review and DOCX generation remain subsequent work.

## Subsequent correctness fixes

Code review reproduced unsafe scientific-token equivalence and timestamp-drift loss/duplication at chunk boundaries. Version 0.3.1 fixes those defects with scientific-case/NFC comparison and versioned overlap alignment, adding regression cases and non-destructive reconstruction of existing runs. Historical outputs above remain historical evidence, not updated accuracy claims. See `FIXES_M1_M3.md` for final validation and real-recording rebuild/review results, and `ISSUES.md` for the remaining milestone gate. No later milestone was started.
