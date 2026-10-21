# Legacy extraction and review pipeline

[Back to the current README](../README.md) · [CLI guide](CLI.md)

This optional workflow is retained for historical compatibility. The default app uses direct rewriting with audio verification off. The `runs/...` paths below describe earlier local examples; their media, models and outputs are not included in a clone. Substitute your own completed run and new output directories. Historical reports record results at the time of each run, not current feature status.

## Historical extraction/review pipeline (`--pipeline legacy`)

Install project dependencies with `.venv/bin/python -m pip install -e '.[dev]'`. Start your local Ollama server and select an installed model with `ollama list`. The default is `llama3.1:8b`; the application never downloads Ollama models automatically.

The following section documents the previous pipeline, available only with `--pipeline legacy`. Its evidence-linked reviews and inline warnings do not apply to the default direct rewrite.

For an existing completed verification run:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document --pipeline legacy \
  --source-dir runs/ctbckfw0pjs-verify-fixed-smoke-01 \
  --output-dir runs/ctbckfw0pjs-document-01 \
  --model llama3.1:8b \
  --source-title 'Technical lecture' \
  --source-url 'https://www.youtube.com/watch?v=CtbckFw0pJs'
```

Use a new output directory for each attempt. In the historical example below, only 90 seconds had been reviewed at that point; the document will disclose uncertain/unchecked evidence. A completed raw transcription directory is also accepted, with all cited audio marked unchecked. No audio is downloaded or re-transcribed by this command. Source title/creator/URL can be supplied for attribution; URLs are stored as text and never fetched. YouTube metadata is used automatically when adjacent to the source run.

If extraction completed but writing failed, reuse its saved knowledge rather than repeating extraction:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document --pipeline legacy \
  --source-dir runs/m1-m4-test-01/verification \
  --reuse-knowledge runs/m1-m4-test-01/document-03 \
  --output-dir runs/m1-m4-test-01/document-new-attempt \
  --model llama3.1:8b \
  --source-title 'Educational video test' \
  --source-url 'https://www.youtube.com/watch?v=CtbckFw0pJs'
```

`--reuse-knowledge` names a prior document run containing completed extraction, not the verification directory. Reuse validates current source hashes, prepared passages, every saved successful extraction request/response and the reconstructed knowledge; altered or incomplete artifacts are rejected before model work. The old run stays immutable, and the new run records reuse provenance/hashes. This skips extraction only; writing and review run afresh. Writing and claim review now update progress and save explicitly incomplete checkpoints.

When a later run has already written/reviewed part of the document, optionally add `--reuse-model-calls PATH_TO_THAT_RUN`. Saved calls are reused only when source hashes/passages, recorded model digest and the complete outgoing request match. Responses are parsed and checked again by current code. Changed prompts/settings use new inference; replayed calls keep their raw responses and source hashes in `model_reuse.json`. Reuse never edits the old run, and consumes the current call budget. Saved replay inputs are limited to 20 MB per artifact and 128 MB total.

If a reviewer returns several assessments for the same requested item, all reasons and original assessments are preserved. The combined result uses the most cautious verdict (`unsupported` before `uncertain` before `supported`; factual `needs_review` before `no_obvious_issue`). Assessments for unknown/wrong items still fail. This handling does not silently discard contradictory evidence.

Outline assembly validates all known concept IDs, removes duplicate references, and restores omitted concepts under their saved topic headings, recording these decisions in `outline.json`. Unknown concept IDs still fail. This preserves concept coverage without asking the model to invent replacement content; it does not certify factual correctness or resolve poor source recognition.

The writer sees extracted concepts rather than the transcript, builds a thematic outline and synthesizes an explanation. Exact source quotes and timestamps support concept citations; separate Ollama passes assess source consistency for every concept/paragraph and scientific plausibility risks for every concept. Ollama selects evidence IDs from a batch-specific schema; the application copies the selected source passages verbatim, so the model cannot alter citation text. One bounded retry is allowed for invalid reference-selection fields; attempts are preserved in `model_calls/` and `extraction_validation.json`. References still undergo separate source-support review. Concept granularity is allocated across all batches from the configured concept/call budgets and recorded in `knowledge.json`; unrepresented passages remain explicit review findings. Extraction progress updates after each batch. Unsupported/uncertain claims, potential scientific errors in the source, altered numeric values or measurement notation, omitted source coverage, unchecked audio and excessive wording overlap produce **visible review flags in Word**. These checks can miss errors: source consistency is not external scientific fact verification. Documents remain AI-generated drafts requiring an educator's review. Failed integrity/schema checks prevent final DOCX delivery and retain failure evidence.

Outputs include `document.docx`, `document.txt`, `document.json`, `knowledge.json`, `evidence.json`, `quality.json`, `prepared_source.json`, a source SHA-256 integrity audit, manifest, and every model request/raw response. Source files are hashed before and after processing; neither raw nor reviewed transcripts are rewritten. Clear salutations/channel chatter are excluded from the prepared copy with an audit; technical examples and uncertainties stay recoverable.

CLI exit codes: **0** source-consistency checks passed (not fact verification), **2** document produced but needs review, **1** processing failure, **130** interrupted. A reviewable draft is not a failed download.

For a new API upload/YouTube job, add `write_document=true` in `/docs` or multipart form data. Audio verification is skipped by default, including document jobs. Add `verify=true` only when you explicitly want the optional second audio pass. Without it, writing uses the completed raw transcription directly; the source remains marked as unchecked. Retrieve `/api/v1/jobs/{id}/document` for Word, or `?format=quality`, `knowledge`, `evidence`, `json`, `txt`. Ollama work runs in the background worker. Raw and reviewed transcripts remain downloadable if writing fails. The current Next.js UI uses direct rewriting; this section documents legacy CLI compatibility.

Writing settings use `VIDEOMIND_WRITE_` followed by: `MODEL`, `ENDPOINT` (default `http://127.0.0.1:11434`, HTTP loopback IP only), `TIMEOUT_SECONDS` (180 per request), `RUN_TIMEOUT_SECONDS` (3600 for model processing), `CHUNK_CHARS` (3500), `MAX_CHUNKS` (80), `MAX_CALLS` (512), `MAX_CONCEPTS` (160), `NUM_CTX` (8192), `NUM_PREDICT` (2200). Requests are non-streaming, schema-constrained and deterministic in settings, but hardware/model nondeterminism remains possible. Finite limits fail explicitly; no silent truncation or automatic retry hides missing evidence. Long lectures may take many minutes and can exceed budgets. Cancellation is checked between model requests, with an active request limited by its timeout. Ollama must run locally; its own configuration determines any server-side behavior. Prompt and response artifacts contain source text; treat them as private project data.

See `MILESTONE_4_5_REPORT.md` for executed checks and remaining limitations.

## Legacy content quality: candidate versus reading copy

Processing completion does **not** establish document quality. The first full-lecture draft contained genuine errors: reversed language-level explanations, garbled ASR terminology, invented elaborations, classroom conversation and verification metadata presented as lesson content. See `DOCUMENT_QUALITY_REVIEW.md`; content-quality acceptance remains open.

New runs retain the full generated candidate in `document.json`. After source/factual-risk review, a content gate withholds paragraphs with blocking findings, failed/missing dependent assessments or pipeline metadata leakage. Remaining candidates receive a topic-aware editorial screen for substantive technical relevance. The exported DOCX/TXT and normal API JSON preview use `reading_document.json`; `content_gate.json` retains withheld paragraphs, reasons and citation-marker edits. Withheld content is not silently replaced by guessed corrections. An empty or partial reading copy is clearly labeled; it must not be presented as a complete lecture reconstruction. Source uncertainty can still require review, and false-negative/false-positive model judgments remain possible.

Word shows review counts rather than reproducing the faulty candidate as an educational explanation or filling the appendix with its unsupported wording. `quality.json`, `document.json` and the content-gate audit retain the diagnostic detail. API `?format=content-gate` exposes the audit; legacy jobs without a reading copy retain their historical JSON behavior.

A separately edited, reference-checked Python guide is available at `runs/m1-m4-test-01/document-reference-corrected-04/document.docx`. It uses 13 official sources and four executed examples. It is a scoped editorial correction, **not** automatic recovery of every word/topic in the lecture and not evidence that the Ollama pipeline now performs authoritative external fact verification.
