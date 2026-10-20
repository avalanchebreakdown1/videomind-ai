# Scientific comparison and boundary stitching fixes

Date: 2026-10-19 (Asia/Tokyo). Package/API version 0.3.1. Scope: the two defects reproduced in the code review. Original transcripts, ASR chunks, audio and prior review reports remain unchanged.

## D1 — preserve scientific distinctions

Old comparison compatibility-normalized and lowercased tokens, then stripped broad leading/trailing punctuation. Controlled examples showed `needs_review: false` for `mW` vs `MW`, `10³` vs `103`, `.5` vs `5`, and a missing function bracket. Those are unsafe equivalences for technical education.

The shared comparison helper now uses Unicode NFC and preserves case, superscripts/subscripts, leading decimal points, numeric punctuation, primes, factorials, ellipses, quotes and brackets. It ignores one trailing full stop/comma only for plain alphabetic prose tokens with at least three letters. Harmless capitalization/formatting differences can be flagged rather than silently equated. Reports/derivatives identify `scientific_nfc_case_sensitive_v2`; historical reviews without this marker retain their older results and should be regenerated into new directories before relying on scientific-token support.

Regression cases include `mW`/`MW`, `ms`/`Ms`, `Co`/`CO`, `10³`/`103`, `x²`/`x2`, `H₂`/`H2`, `.5`/`5`, `x′`/`x`, `n!`/`n`, `f(x)`/`f(x`, mathematical punctuation and ellipses. Canonically equivalent Unicode still matches. This is conservative lexical comparison, not symbolic algebra, unit conversion or fact verification.

## D2 — reconcile overlaps before ownership decisions

Old stitching independently retained each word if its own midpoint belonged to that chunk's core. At a 10-second boundary, the same word at 9.6–9.9s and 10.1–10.4s was emitted twice. Reversing those candidates discarded both. Both were reproduced by failing regression tests before the implementation change.

New `overlap_alignment_v2` validates source order/timestamps, then performs monotonic one-to-one alignment in the shared audio region, with at most one second of midpoint drift. It maximizes matching occurrences, minimizes timestamp disagreement and emits each matched occurrence once. Multiple real repetitions remain separate occurrences; there is no global phrase deduplication.

Words found in only one candidate are retained and flagged. Incompatible hypotheses for overlapping time are alternatives, not concatenated speech: one source sequence is selected and both are retained in `stitching.json`. Isolated single-word matches, drift, conflicting candidates, ordering reconciliation and absent shared context remain explicit review issues. With overlap disabled, adjacent repetitions are preserved and a nonzero boundary review window is recorded. The matrix has a 100,000-cell cap; excessive token density fails explicitly while preserving original ASR chunk outputs.

Text/timestamps alone cannot distinguish every genuine repetition from a shifted duplicate. Single-word ambiguity and drift beyond the matching tolerance are not claimed solved without audio review. M3 prioritizes recorded stitching issues, retains known but unchecked uncertainty, exposes per-word `audio_reviewed`, and reports unreviewed boundary spans.

## Compatibility and reconstruction

New primary manifests record the stitching version and save `stitching.json`. Verification validates reconstruction using that version. Historical runs without the marker are validated using `midpoint_v1`, preserving compatibility and exact original bytes. Unknown versions fail explicitly; new-version runs require their stitching evidence.

`videomind restitch` reconstructs into a new directory from saved original ASR chunk outputs, without YouTube access or rerunning primary ASR. It copies normalized audio/chunk evidence without hard links, writes the new assembly and boundary evidence, and records original-source hashes/counts in `restitching.json`. Source hashes are checked after reconstruction. Existing directories and destinations inside the source run are rejected.

```bash
env -u PYTHONPATH .venv/bin/python -m videomind restitch \
  --run-dir 'runs/ctbckfw0pjs-test-01~/transcription' \
  --output-dir runs/my-rebuilt-transcript
```

Then verify the rebuilt run into another new directory. Old source/review artifacts are not silently corrected or overwritten.

## Files changed

Created `services/text_service.py`, `services/restitching_service.py`, `restitch_cli.py`, `tests/test_restitching.py`, this report and `ISSUES.md`.

Updated stitching, pipeline export/versioning, verification comparison/source validation/uncertainty propagation, CLI dispatch, package/API version, scientific/boundary/integration regression tests, contributor instructions and architecture/API/requirements/roadmap/README documentation. No dependencies or system configuration changes were required.

## Executed validation

The initial targeted run reproduced ten failures in eleven selected cases (the prime-symbol case was already correctly distinguished). Implemented fixes then passed the expanded scientific, repetition, ordering, ambiguity, budget, source-preservation, legacy-validation and reconstruction tests.

Complete suite command:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -o addopts=''
```

**259 tests passed**, including all prior M1–M3 checks and three real-ASR tests. Local API tests ran with approved socket access outside the restricted sandbox. No external YouTube requests or new model downloads were needed. Package 0.3.1 installed locally, dependency check passed and the new CLI help entry point passed.

## Actual recording: preserved original and separate rebuilt run

Original: `runs/ctbckfw0pjs-test-01~/transcription` — 13 chunks, 3767.228688 seconds, 10,095 assembled words.

Created: `runs/ctbckfw0pjs-restitch-fixed-01` — 10,103 assembled words, with all 12 boundaries retaining review evidence. The net eight additional selected words came from existing ASR candidates; they are not invented or proof of improved accuracy. Original TXT/JSON/chunks/manifest/audio hashes still match. Both original legacy and rebuilt runs validate; the rebuilt run contains exact copies of original chunk/audio content.

Re-verified three sections using cached `small` against primary `tiny.en`:

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind verify \
  --run-dir runs/ctbckfw0pjs-restitch-fixed-01 \
  --output-dir runs/ctbckfw0pjs-verify-fixed-smoke-01 \
  --model small --max-sections 3
```

Completed without failed sections. It reviewed 90 seconds (2.389% core-time coverage): 106 words supported, 320 uncertain and 9677 not checked. Some uncertain words are in known **unreviewed** assembly regions, distinguished by `audio_reviewed: false`; they were not all evaluated by the second ASR. The 15 unresolved spans comprise the three reviewed-but-uncertain sections plus twelve unchecked boundary regions. The rebuilt raw/evidence/audio hashes remained unchanged.

Inspect `runs/ctbckfw0pjs-verify-fixed-smoke-01/verification.json`. This is a bounded integration check, not a full-hour accuracy evaluation. No M4/M5 or UI work was started. Remaining M1–M3 acceptance/reliability work is explicitly tracked in `ISSUES.md`; these two fixes do not close every limitation.
