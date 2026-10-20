# M4/M5 — local knowledge extraction, original writing and Word export

**Content-quality acceptance remains open.** The later user review found genuine errors in the generated lecture document. Historical processing/test results below do not establish educational accuracy. See `DOCUMENT_QUALITY_REVIEW.md` for the correction and current status.

Implemented on 2026-10-19, package version 0.4.0, following explicit user authorization to implement writing/export. Previous M1–M3 defects remain fixed; their outstanding accuracy/reliability limits remain open in `ISSUES.md`. No frontend or external factual-verification service was added.

## Implemented behavior

1. Load a completed raw transcription or separate verification run. Reconstruct/validate raw runs using their recorded stitching version; regenerate the prepared source from reviewed words and reject inconsistent saved preparation. Preserve source transcripts/evidence and audit file SHA-256 values before/after processing.
2. Prepare a separate technical source excluding clear salutations/channel chatter, retaining exclusions, source character spans, timestamps, technical examples and uncertainty.
3. Extract bounded batches into concepts with explanations, prerequisites, caveats and exact source quotations. Assign stable concept/evidence IDs in application code. Unknown references and altered quotations fail validation.
4. Use Ollama to plan a thematic educational outline and write explanations from the concept inventory. The writer receives no original transcript/quotes. Original source wording remains available separately for reviewers. This design encourages synthesis; it does not prove originality or educational completeness.
5. Run a separate source-consistency assessment for every concept and paragraph, plus a separate scientific plausibility risk screen for every concept. Detect/report unsupported or ambiguous claims, potentially false source claims, numeric/unit changes, source coverage gaps, uncertain/unchecked audio and excessive lexical similarity. An unreliable concept also flags its dependent writing. Plausibility uses model knowledge as a fallible risk signal, never authoritative evidence.
6. Export a new DOCX with title/subtitle, technical headings, readable styles/margins, header/page numbers, source attribution, per-paragraph evidence references, timestamp/status table and conspicuous review flags. Retain generated TXT/JSON, structured knowledge, evidence, quality report and integrity audit alongside it.
7. Persist all model requests, unmodified response JSON, settings, installed model digest, failures and run state. Malformed/truncated output, invented IDs/quotes, budget exhaustion, model changes and source mutation prevent final DOCX delivery; partial evidence remains.
8. Add `videomind document` for existing runs and `write_document=true` for API jobs (automatically enables audio verification). The existing worker performs writing in the background. `/document` serves DOCX or writing/quality/knowledge/evidence outputs. A writing failure preserves raw/reviewed transcript and verification-report downloads.

`state=completed` means processing finished. `quality_state=needs_review` marks a draft with findings. Even `source_consistent` is not scientific certification: **external scientific fact verification is not implemented**. An educator must check claims and authoritative references before publication/teaching. The application never substitutes inferred corrections into the original transcript.

## Files

- New: `writing_config.py`, `writing_cli.py`, `services/knowledge_models.py`, `services/ollama_service.py`, `services/understanding_service.py`, `services/rewriting_service.py`, `services/quality_service.py`, `services/writing_pipeline.py` under `backend/videomind/`.
- Extended: `services/document_service.py`, `cli.py`, `worker.py`, `api.py`.
- Tests: `tests/test_writing.py` (38 controlled cases).
- Dependencies: `python-docx`, direct Pydantic declaration; lock includes python-docx 1.2.0 and lxml 6.1.3. Package installed editable at 0.4.0 in the project venv. No system-wide installation.
- Updated: README, architecture, requirements, API, development plan, contributor instructions and issue tracker.

## Executed checks

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q
```

**297 passed in 27.60 seconds**, including the three opt-in real ASR smoke checks. Default selection excludes those three cached-model tests; the default suite uses injected model responses and no model/network downloads. TestClient tests ran with normal local sockets because the sandbox stalls its thread/event-loop wakeups.

The 38 writing tests include actual DOCX reopening/XML package checks, formatting/attribution, unchanged source bytes, controlled hallucinations, copied passages, changed measurement case/superscripts, source uncertainty, scientific risk flags, unsupported IDs/quotes, malformed/truncated responses, missing review, unavailable models, model digest changes, source tampering, finite budgets/context limits, cancellation and an upload → verification → writing → Word download integration. Failure integration confirms both transcripts and the verification report remain accessible.

`env -u PYTHONPATH .venv/bin/python -m pip check`: **No broken requirements found**. Tests and package commands unset inherited ROS `PYTHONPATH`.

### Real Ollama smoke

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document \
  --source-dir runs/smoke-final \
  --output-dir runs/ollama-document-factual-review-01 \
  --source-title 'Local renewable energy speech sample' \
  --model llama3.1:8b
```

The installed local model completed extraction, thematic writing, source review, scientific-risk screening and DOCX export. The model digest was `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`. Nine requests/responses are preserved. Result: `runs/ollama-document-factual-review-01/document.docx`, successfully reopened with python-docx. Source hashes were independently rechecked after completion.

The command correctly returned **2** for a generated draft requiring review: five findings (one source coverage gap and four concept/paragraph warnings for unchecked audio). Scientific-risk assessments reported no obvious issue; this is not external validation. The example uses a short synthetic-speech renewable-energy transcript, not the hour-long lecture. Earlier development smoke directories remain untouched.

## Limits and next work

- Model consistency/plausibility checks can miss false claims and prompt injection. The same Ollama model performs different tasks; those tasks do not provide independent corroboration. Scientific truth requires authoritative evidence/human review beyond this implementation.
- Similarity, numeric and measurement checks are heuristics. They cannot guarantee originality, copyright compliance, semantic equivalence or complete mathematical integrity. Technical notation is Unicode text, not native Word equation objects.
- Documents with findings are marked drafts; no silent rewriting removes uncertainty. Model output can still be repetitive or omit important ideas; coverage findings and saved evidence support review.
- Extraction/context/concept/call/deadline limits are explicit. Oversized inputs fail instead of silently truncating. Full-length lecture writing/accuracy has not been benchmarked, and failed writing has no resume; retry into a new directory. Cancellation is cooperative between requests; an active Ollama request is bounded by its configured deadline.
- No media/diagram understanding, website, multi-user hosting, storage quota or independent external scientific reference retrieval was added. Earlier M1–M3 limitations remain in `ISSUES.md`.

Next acceptance work is to review an authorized full technical lecture against audio and authoritative facts, then evaluate document quality/coverage. The dedicated frontend is a later milestone and was not started.

Implementation reference: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) (`/api/chat`, JSON-schema `format`, non-streaming responses). The client uses only a configured loopback IP, never fetches attribution URLs, follows no redirects/proxies, and does not pull models.

## Follow-up: exact-citation regeneration after the user's lecture test

The user's full audio review completed with 100% coverage, 126 uncertain sections and zero failed sections. Uncertainty does not mean every word is wrong. Document extraction then stopped on its 11th model call: citation E0113 capitalized the source's `if you want…` as `If you want…`. Exact-match validation correctly rejected it; no final Word file was delivered.

`understanding_service.py` now requests literal case/punctuation copying and allows exactly one batch regeneration on an invalid citation. All citations are validated before adding any concepts from that batch. Failed and replacement responses remain separate, and `extraction_validation.json` records batch, attempt, model-call number and problem reason. A second invalid attempt fails explicitly. This does not relax scientific-symbol matching or invent replacement wording. The retry shares the existing model-call/deadline budgets and cancellation checks.

Executed follow-up checks: **298 passed, 3 deselected in 19.76 seconds** using the default offline suite. Four added regression cases cover recovery and persistent case/numeric/unit/superscript changes. No audio/inference integration was changed, so the real ASR tests were not repeated for this fix.

A targeted live Ollama test replayed the user's invalid saved response, then requested one fresh retry for exactly that batch. It succeeded with three concepts and two total calls (one replay, one live); failed-run evidence hashes were unchanged. Results are in `runs/citation-retry-smoke-01/`. Existing `runs/m1-m4-test-01/document/` and all transcripts/review evidence remain untouched.

The full source contains 77 extraction batches. Full-lecture writing has not been rerun here and remains an acceptance task; concept/call/context limits may still need longer-source work. Retry document generation in a new directory, reusing the completed verification output. Do not download/transcribe/review the hour of audio again for this citation failure.

## Follow-up: replace model-written quotations with source-reference selection

The user's next attempt failed in batch 17 even after the retry. The retry-only approach was insufficient for long transcripts. It is superseded by `application_copied_passage_v1`:

- The extraction schema now permits only evidence IDs from the current batch, with no model-generated `quote` field. The application copies complete selected source passages into canonical citations, preserving original characters and whitespace. This eliminates model copying/formatting errors without case folding, fuzzy matching or guessed corrections.
- ID selection alone does not establish factual support. All extracted concepts and generated paragraphs still receive the existing separate source-consistency review; scientific plausibility/uncertainty checks remain intact. Invented IDs, unexpected fields or unsupported claims are not automatically accepted.
- One bounded retry remains for malformed reference selections, with both calls and validation records preserved. Full original source and failed runs remain unchanged.
- Extraction granularity is allocated across every source batch using the configured concept/call budgets, rather than accumulating concepts until a predictable late limit failure. The allocation is recorded as `concept_budget_per_batch`; every batch is still processed and unrepresented passages remain quality findings. This allocation is not proof of complete concept coverage, and the existing runtime/context/call limits still apply.
- Extraction now reports progress after each batch. The outline catalog is compacted and allows grouping up to eight concepts per section, consistent with its schema. Unknown/omitted concept references still fail validation.

Validation: **302 passed, 3 deselected in 20.41 seconds** with the full default offline suite. Tests include application-copied quotations preserving Unicode/case/measurement notation/whitespace, batch-specific ID constraints, rejection of unexpected model quotation fields, and 77-batch budget/progress coverage. Audio/inference integration was not changed.

Live Ollama checks succeeded for both formerly failing batches (11 and 17), with one request each; evidence is in `runs/reference-selection-smoke-01/`. A new short end-to-end extraction → writing → reviews → DOCX run also completed in `runs/reference-selection-document-smoke-01/` (reviewable draft, six findings, CLI exit 2). The DOCX was reopened successfully and source integrity was checked. The user's verification files were checked against the source hashes recorded by `document-02` and were unchanged.

These are targeted regression and short end-to-end checks, not a claim that the full hour-long lecture now passes end to end. Continue acceptance testing into a new output directory such as `document-03`; the completed audio review is reusable.

## Full-lecture writing recovery and validation

The user's `document-03` completed all 77 extraction batches but its global outline omitted six concept IDs. The former membership gate aborted instead of retaining the remaining extracted knowledge. This is now handled by application-side assembly: reject unknown IDs, deduplicate references, and append omitted concepts under their original topic headings. `outline.json` records assembly decisions. Writing uses groups of at most two concepts to bound downstream review contexts and retains every known concept.

Recovery additions:

- `--reuse-knowledge` validates source hashes/prepared passages and reconstructs the saved knowledge from every original successful extraction response. It rejects altered knowledge, unsupported reference IDs, changed sources and incomplete extraction. Source/extraction hashes are audited again after generation. Old runs are never modified.
- `--reuse-model-calls` requires matching source hashes/passages and model digest, then reuses only byte-equivalent structured outgoing requests (canonical JSON comparison). Every response is parsed/validated by current code again; changed prompts/settings require new inference. Replay provenance/hashes are saved in `model_reuse.json`; replay inputs have finite per-file/aggregate size limits. This is exact-request replay, not blind acceptance of partial documents or quality checkpoints.
- Multiple source assessments for the same item retain all original assessments/reasons and use the most cautious verdict: unsupported > uncertain > supported. Multiple factual-risk assessments retain `needs_review` over `no_obvious_issue`. Wrong-item assessments still fail. This addressed the real reviewer response for C0046, which supplied both supported and unsupported clause assessments.
- Writing/review progress and explicitly incomplete diagnostics are saved between requests. The default model-call budget is now 512, preserving an explicit upper bound while allowing extraction, writing, scientific review and source review for the hour-long case with retry headroom. Cancellation/context/deadline limits remain.
- New modules: `services/knowledge_reuse_service.py`, `services/model_reuse_service.py`. Updated writing CLI/pipeline, outline assembly, model session, quality service, configuration and documentation.

### Executed full recovery

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document \
  --source-dir runs/m1-m4-test-01/verification \
  --reuse-knowledge runs/m1-m4-test-01/document-03 \
  --reuse-model-calls runs/m1-m4-test-01/document-recovered-01 \
  --output-dir runs/m1-m4-test-01/document-recovered-03 \
  --model llama3.1:8b \
  --source-title 'Educational video test' \
  --source-url 'https://www.youtube.com/watch?v=CtbckFw0pJs'
```

**Completed successfully**, CLI exit **2** because quality findings require review. Output: `runs/m1-m4-test-01/document-recovered-03/document.docx` (60,507 bytes), reopened successfully with python-docx. The recovered document contains all **77 concepts**, **21 sections**, and **78 paragraphs**. It completed **155 source-consistency assessments** and **77 scientific-risk assessments**. Of 273 model calls in the new run, **132** were replayed from exact saved requests and **141** used live local Ollama. Audio verification and knowledge extraction were not repeated.

Independent final hash checks confirmed the original primary transcript/chunk/manifest artifacts and normalized audio still match their recorded verification hashes. The verified source, reused extraction and replay artifacts also passed preservation checks. Counts, source integrity and DOCX readability are recorded in `acceptance_audit.json` alongside the new document. Earlier failed recovery directories remain preserved, including the input-size diagnostic that led to separating saved-source limits from HTTP-response limits.

Quality state is **needs_review**, with **344 findings**: 107 unsupported source-consistency assessments, 155 source-audio uncertainty flags, 18 factual-risk flags, 4 measurement/notation mismatch flags, 58 propagated unreliable-concept flags, one source-coverage gap and one unresolved-audio notice. These overlap and are fallible model/heuristic findings, not 344 independently proven factual errors. Similarity checks completed with no excessive-overlap flags. No source-derived claim is certified scientifically true; the generated document remains a marked draft requiring educator review.

### Final tests

`env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q`: **317 passed in 28.88 seconds**, including all three cached-model real ASR checks. Default offline selection: **314 passed, 3 deselected in 22.53 seconds**. Coverage now includes the six omitted lecture concepts, duplicate/unknown outline references, immutable extraction reuse, changed source/knowledge/response rejection, exact-request replay and mismatch behavior, model digest changes, larger saved sources, and conservative conflicting-assessment handling.

This establishes full-lecture processing/recovery and preserved source evidence. It does not establish educational completeness or scientific accuracy acceptance. Next work is human review of the draft against the source audio and authoritative references, then revision/evaluation of the flagged material; no frontend or later milestone was started.
