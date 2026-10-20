# Direct transcript rewriting: implementation and full-lecture review

Subsequent shorter-video testing and example/schema fixes are recorded in [SHORT_VIDEO_TEST.md](SHORT_VIDEO_TEST.md). That test's latest suite result is 353 passed; the full-lecture runs and counts below describe the earlier acceptance pass and remain unchanged.

The direct rewriting workflow is implemented and tested. **Content acceptance has not passed.** Removing the former extraction/review stages reduces processing work but does not prevent a local model from generating inaccurate technical explanations.

## Implemented behavior

The CLI `document` command and API document jobs default to direct rewriting. The same installed Ollama model receives each bounded transcript section with preceding and following context. The default direct section budget is 6,000 characters, configurable through `VIDEOMIND_WRITE_DIRECT_CHUNK_CHARS`. No concept extraction, outline, secondary LLM review, or content gate runs on this path. The former workflow remains explicitly available through `--pipeline legacy`; its recovery options require that mode.

The editor is instructed to preserve technical explanations, worked examples, qualifications, units, and mathematical notation; remove chatter; and use context to repair recognisable terminology and conceptual confusions. It should omit irrecoverable fragments rather than manufacture measurements, dates, or citations. Contextual completions are editorial additions, not recovered speech. Word contains clean prose, formatted code, headings, page numbers, and attribution, without inline uncertainty markers.

All original transcripts and historical artifacts remain unchanged. Each attempt requires a new directory. Exact source spans, all model requests/responses, model digest/settings, model-reported corrections, code exclusions, and editorial removals are saved separately. Corrections are not a complete semantic diff or independently verified facts. Candidate output is preserved as `candidate_document.json`; readable output is `document.json` / `reading_document.json` plus TXT and DOCX.

Generated code introducing absent identifiers/literals or an import not actually discussed locally is excluded with an audit. Fenced code inside a prose block also receives these checks. Clear greetings, classroom logistics, motivational boilerplate and orphaned labels from excluded code are removed with an audit. These limited rules do not establish general semantic relevance, scientific truth, or complete coverage.

API previews/downloads serve the direct document schema (sections containing paragraph/code blocks). New fixed report formats are `rewrite-audit` and `source-chunks`; absent legacy knowledge/evidence/gate reports return 404. Public artifact lists advertise existing files. The API still skips audio verification unless explicitly requested.

## Full lecture execution

Input: `runs/m1-m4-test-01/transcription`, the complete **3,767.23-second (62.8-minute)** recording previously ingested from `https://www.youtube.com/watch?v=CtbckFw0pJs`. This test reused its completed transcript; it did not repeat downloading or primary ASR.

| Attempt | Model and processing | Result |
| --- | --- | --- |
| `document-direct-01` | llama3.1:8b, 17 live calls, approximately 192 seconds | Generated; review exposed invented code, factual errors and chatter. Preserved as diagnostic evidence. |
| `document-direct-02` | llama3.1:8b, 17 live calls, approximately 191 seconds | Generated with stronger instructions and initial code filtering; still made factual errors. |
| `document-direct-03` | qwen2.5-coder:7b, 10 live calls, approximately 270 seconds | Full larger-context run with following-context hints and stronger code checks. Some terminology improved; technical errors remained. |
| `document-direct-04` / `document-direct-05` | Exact recorded requests/responses from attempt 03, rerun through the updated deterministic reading cleanup | No new inference. Request equality checked for every call, prior artifacts hash-checked unchanged, and replay provenance recorded. Attempt 05 is the latest reading copy. |

The final copy is `runs/m1-m4-test-01/document-direct-05/document.docx`. All **55,601 transcript characters** were submitted across ten chunks. It has 27 sections / 35 blocks; 11 generated code blocks were excluded and 17 boilerplate sentences removed. The model reported 47 corrections, of which 34 original excerpts matched the local source exactly; this is explicitly not 47 certified factual corrections. Word ZIP/readability checks passed. No inline uncertainty markers or invalid `import python` remain. Four manually inspected, bounded printing/arithmetic examples executed with the expected results.

Full review evidence is in `runs/m1-m4-test-01/direct-rewrite-review-01/review.json`. All primary transcript/evidence/audio hashes remained unchanged. `replay_integrity.json` proves attempt 03 was not modified while producing the reading copy.

## Content review: remaining failures

- The model overgeneralizes automatic type conversion and describes rebinding a name as conversion. A controlled `10 + "20"` check raises `TypeError`; rebinding a name from an integer to a string does not convert the original integer object. Python documents objects/types and assignment separately. References: [data model](https://docs.python.org/3.13/reference/datamodel.html), [assignment statements](https://docs.python.org/3.13/reference/simple_stmts.html).
- A Hadoop naming/logo digression gains a speculative explanation absent from the local source.
- The source discusses semicolons, but the generated explanation omits that topic. Submitting every character does not guarantee retention of every important detail. Python permits semicolon-separated simple statements: [language reference](https://docs.python.org/3.13/reference/simple_stmts.html).
- Corporate usage details, mappings of borrowed language features, and claims of reduced type errors remain unsubstantiated. The [official Python FAQ](https://docs.python.org/3.13/faq/general.html) supports the ABC background and Monty Python naming account, rather than every generated embellishment.
- Repeated introductions, type explanations, and application lists remain. Exact duplicate-block removal is not global semantic consolidation.

No additional LLM review or external fact-retrieval service has been added to the product. The reference checks above were part of this requested review. The supplied Word document is a generated draft, **not an accepted accurate technical guide**. These failures remain visible here and in the separate review report, not as inline uncertainty flags in the document.

## Tests and changed files

Final command: `env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q` — **349 passed in 31.94 seconds**, including the three cached real-ASR smoke checks. Default tests remain offline; live lecture runs explicitly used installed local Ollama models without downloading models.

Tests cover default API/CLI direct dispatch without secondary ASR, context correction auditing, unit/code rendering, exact source preservation, full character-span chunking, code imports/fenced-code checks, actual classroom-boilerplate failures, empty/malformed/truncated/unavailable generation, bounded retries, failure artifact withdrawal, raw-transcript availability after writing failure, API fixed report formats, and legacy extraction/review regressions.

Implementation: `backend/videomind/services/direct_rewrite_service.py`, `services/writing_pipeline.py`, `services/ollama_service.py`, `services/document_service.py`, `writing_config.py`, `writing_cli.py`, and `api.py`. Regression coverage: `tests/test_direct_rewrite.py` and the retained legacy checks in `tests/test_writing.py`. README, API design, and contributor instructions describe the new default.

The next acceptance work is factual correctness and technical coverage of the direct rewrite. Subsequent milestones should not be justified by the successful processing/test count alone.
