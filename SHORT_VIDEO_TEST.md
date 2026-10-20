# Short-video test — 2026-10-20

Source: [Learn Python in Less than 10 Minutes for Beginners (Fast & Easy)](https://www.youtube.com/watch?v=fWjsdhR3z3c), Indently. Actual downloaded audio duration: **629.969 seconds**, approximately 10½ minutes.

The accessible audio was downloaded through the existing guarded YouTube ingestion service and transcribed with the cached Faster-Whisper `small` checkpoint on CPU/int8. No models were downloaded and no second audio-verification pass ran. The complete raw transcript contains **10,637 characters**.

## Outputs

- Raw transcript: `runs/fwjsdhr3z3c-test-01/transcription/raw_transcript.txt` (original JSON, chunks and audio evidence also retained).
- Latest Word draft: `runs/fwjsdhr3z3c-test-01/document-04/document.docx`.
- Readable notes: `runs/fwjsdhr3z3c-test-01/document-04/document.txt`.
- Correction/exclusion audit: `runs/fwjsdhr3z3c-test-01/document-04/rewrite_audit.json`.
- Validation and content observations: `runs/fwjsdhr3z3c-test-01/review.json`.

The draft has **10 sections and 15 code blocks**. Adjacent code blocks within each section compile when combined; they were syntax-checked rather than executed. Input/infinite-loop examples were not run. Original transcript/evidence hashes remained unchanged, every transcript character was submitted, the DOCX ZIP/readability checks passed, and no inline uncertainty markers were added.

The two live local Qwen calls in `document-03` produced the final model content. `document-04` exactly replays those saved requests/responses through the corrected code checks, with no new inference; `replay_integrity.json` records provenance and confirms the prior directory stayed unchanged. Earlier attempts remain available in `document`, `document-02`, and `document-03`.

## Fixes exposed by this test

The original filter incorrectly treated explanatory comments, spoken numbers, reconstructed local names, f-string syntax and context-supported conversion/exception names as invented dependencies. The updated check retains these while continuing to reject unsupported imports, calls and unrelated literals. It now recognizes spoken identifiers such as “item name” as `item_name` and a discussed integer-conversion exception as `ValueError`.

The model also mislabeled prose as code and produced code-only sections. Its output schema now requires a separate prose explanation for each section, with code examples in their own field. Up to six sections per chunk and explicit end-of-chunk coverage instructions replace the former three-section limit. This remains a single-model direct rewrite, without additional extraction/review passes.

Implementation changes are in `backend/videomind/services/direct_rewrite_service.py`; controlled regressions are in `tests/test_direct_rewrite.py`. README reflects the updated example-retention policy.

Final suite: `env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q` — **353 passed in 32.49 seconds**, including the three cached real-ASR smoke tests. Added checks cover valid local names/comments/spoken numbers, reconstructed function names, snake_case identifiers, conversion builtins, f-string syntax and conversion exceptions; unsupported calls/imports/literals remain covered.

## Review limitations

Processing passed; this is still a generated educational draft. The principal topics are present: variables, types, conversion, arithmetic, conditions, loops, input/break, functions and exception handling. The recording's `pass` explanation is still omitted. Naming uniqueness and explicit-conversion wording need qualification. Some examples contain only setup values or adjacent fragments, rather than complete demonstrations. The reconstructed while-loop example prints 0–4, whereas the transcript describes 1–5. No external factual-verification service was used.
