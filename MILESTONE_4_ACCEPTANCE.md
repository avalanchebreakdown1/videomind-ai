# Milestone 4 acceptance recheck — 2026-10-19

**Subsequent content review found genuine errors.** This report records processing checks, not educational-content acceptance. See `DOCUMENT_QUALITY_REVIEW.md` for reproduced failures, code changes, the corrected reference-backed guide and remaining work.

The user requested a complete test and document generation without errors. The following checks completed with no processing failures. Content quality remains a separate acceptance criterion; no unsupported claims or uncertainty flags were removed to obtain a passing result.

## Executed checks

| Check | Result | Scope |
|---|---|---|
| `env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q` | **317 passed in 28.29 seconds** | Includes all three cached-model real ASR smoke checks, URL/upload/job tests, verification disagreements, content integrity, recovery and DOCX tests. External YouTube responses in automated tests are mocked. |
| Full-lecture document regeneration | **Completed**, no processing error | Used validated saved knowledge and 273 exact matching saved Ollama responses; all writing/review/export logic ran again. Did not download the video or repeat hour-long audio review. |
| Fresh local Ollama writing test | **Completed**, no processing error | Short renewable-energy transcript processed through fresh extraction, outline, writing, source/factual-risk reviews and Word export, with no saved model-call replay. |
| Word artifact inspection | **Passed** | Both files reopen with python-docx and pass ZIP integrity checks. |
| Lecture preservation/coverage audit | **Passed** | Original primary/chunk/manifest and normalized-audio hashes match verification records; current verified source hashes match; all 77 extracted concepts remain represented. |

## Generated artifacts

- Full lecture: `runs/m1-m4-test-01/document-acceptance-01/document.docx`
- Full lecture audit: `runs/m1-m4-test-01/document-acceptance-01/acceptance_audit.json`
- Full lecture quality report: `runs/m1-m4-test-01/document-acceptance-01/quality.json`
- Fresh local-model sample: `runs/document-live-acceptance-01/document.docx`
- Fresh sample model requests/responses: `runs/document-live-acceptance-01/model_calls/`

Both CLI commands returned **2**, the documented status for a generated document requiring content review. Their manifests record `state=completed` and no processing error. Exit 2 is not suppressed or converted into unconditional success.

The lecture retains **344** overlapping model/heuristic findings, including source-audio uncertainty, potentially unsupported claims and factual risks. The fresh short sample retains **6** findings. These are review signals, not independently proven error counts. Scientific accuracy, complete educational coverage and publication readiness have not been established.

No new processing defect was reproduced, so no implementation changes were needed for this recheck. Original runs, transcripts, verification evidence and prior documents remain untouched. New files are limited to the separate acceptance output directories and this report.

## Practical conclusion and remaining work

The tested workflows can generate Word documents without processing failures. This is not a guarantee that every fresh model response, future YouTube URL or arbitrary source will succeed, and the full-lecture regeneration here deliberately reused recorded inference. The independent fresh Ollama test used a short source, not a new hour-long inference run.

Before calling the lecture document final, review the flagged claims against source audio and authoritative references, resolve recognition uncertainty in a separate derivative, and evaluate the resulting explanation. Existing M1–M3 reliability/accuracy limits remain in `ISSUES.md`. No further milestone or UI work was started.
