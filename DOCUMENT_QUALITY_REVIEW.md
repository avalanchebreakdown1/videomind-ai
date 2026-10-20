# Document content-quality failure and correction

The user correctly reported many errors in the generated document. Earlier test/acceptance reports establish software execution and artifact integrity, not adequate educational content. Milestone 4 **content-quality acceptance remains open**.

## Reproduced problems

- P0010/C0012 reverses the high-level/low-level explanation and invents a misleading account of communicating with the computer.
- C0001/P0001 turns session-start requests into a technical concept. C0009/P0077 promotes classroom/family banter into purported educational content.
- C0015, C0033, C0039 and C0053 treat garbled terms such as “Paita”, “Kama Being” and “Intertype” as concepts rather than unresolved recognition problems.
- P0043 describes uncertainty in verification statuses as though it were a property of Python's typing rules.
- The writer adds claims absent from the selected concepts/source. The old export printed those paragraphs despite its own review findings.
- Some review findings are themselves unreliable: treating “easy” versus “very easy” as unsupported merely because the words differ, or treating ordinary words after years/numbers as measurement units. The 344 flags are not 344 independently established errors.

The causal chain is weak primary ASR → unreliable concept selection → elaboration by the writing model → a diagnostic review that did not prevent publication in the reading body. Different Whisper passes and separate prompts to the same Ollama model do not establish scientific truth. Primary transcripts remain unchanged.

## Implementation changes

- `services/content_gate_service.py`: withhold paragraphs with blocking claim/factual/number/unit/similarity findings, missing supported dependent assessments, unresolved factual risks or pipeline-metadata leakage. Editorial screening considers the document's main subject and supplied source context; classroom dialogue, vague filler and off-topic discussion are not automatically technical merely because a section heading exists.
- Model-generated parenthesized concept citations can be removed from retained reading text when they are absent from source quotes; all edits retain original/generated text in the audit. Literal source identifiers and technical examples are preserved.
- `writing_pipeline.py`: retain original `document.json`; save filtered `reading_document.json` and full `content_gate.json`. DOCX/TXT publish the filtered reading copy. Withheld paragraphs and incomplete coverage remain explicitly disclosed; an empty reading copy is not advertised as a successful complete educational explanation.
- `document_service.py`: show only retained evidence references and a compact findings summary in the gated Word output. Do not reprint rejected candidate prose as curriculum or bury it in a long diagnostic appendix. Add a separate generic reference-guide renderer that requires known citations for every edited paragraph/example; rendering alone does not fact-check its input.
- `api.py`/`worker.py`: normal JSON document previews serve the reading copy when present, expose the content-gate audit, and report gate status. Preserve legacy-run behavior and raw/candidate evidence.
- `quality_service.py`: evaluate semantic entailment rather than requiring verbatim paraphrases; recognize measurement units instead of arbitrary alphabetic words following a number; preserve genuine code/technical examples containing greetings.
- Extraction/writing prompts explicitly exclude classroom logistics, employment promises and garbled pseudo-concepts, and prohibit treating ASR metadata as subject-matter facts. Prompts are safeguards, not guarantees.

## Corrected deliverable

`runs/m1-m4-test-01/document-reference-corrected-04/document.docx` is a **separately edited, reference-checked Python study guide** with eight sections, 13 official references and four newly authored, executed code examples. It corrects language/implementation distinctions, name binding and type semantics, semicolon support, function/module concepts and historical naming. It excludes unsupported career promises, corporate-usage assertions, classroom banter, ambiguous names, and Java/Hadoop/platform claims needing separate references.

This guide is not the raw transcript, not a complete reconstruction of the lecture, and not an automatic Ollama-only correction. `document.json`, `references.json`, `editorial_audit.json` and `source_integrity.json` disclose its scope, sources, exclusions and checks. Original draft/transcript/audio files remain unchanged. The guide is original educational prose; external factual support is attributed rather than silently presented as recovered speech.

Primary references include the [Python FAQ](https://docs.python.org/3.13/faq/general.html), [CPython bytecode documentation](https://docs.python.org/3.13/library/dis.html), [execution model](https://docs.python.org/3.13/reference/executionmodel.html), [data model](https://docs.python.org/3.13/reference/datamodel.html), [statement grammar](https://docs.python.org/3.13/reference/simple_stmts.html), [built-in types](https://docs.python.org/3.13/library/stdtypes.html), [lexical analysis](https://docs.python.org/3.13/reference/lexical_analysis.html), [functions](https://docs.python.org/3.13/tutorial/controlflow.html), [modules](https://docs.python.org/3.13/tutorial/modules.html), [history](https://docs.python.org/3.13/license.html), [applications](https://www.python.org/about/apps/) and [comparisons](https://docs.python.org/3.13/reference/expressions.html#comparisons). The complete numbered list is in the new document. Four example outputs were checked with the project Python interpreter; both DOCX package integrity and readability were checked.

## Live regression evidence

The gate was applied to the actual saved faulty candidate and its saved review, with fresh local Ollama editorial checks. Results in `runs/m1-m4-test-01/document-content-gate-02/`: **72 of 78 candidate paragraphs withheld**, six retained, original inputs unchanged. Previously published “mission computer”, “Paita development”, verification-status narration and classroom-parental content are absent from the exported reading copy. This is an incomplete diagnostic reading copy, not the corrected eight-section guide above and not proof the six retained paragraphs are all factually correct.

A separate fresh Ollama extraction → writing → reviews → content gate → DOCX test completed in `runs/document-content-gate-live-01/`. It retained review flags and did not silently certify content. External fact retrieval was not enabled in the application.

## Remaining acceptance work

Reliable automatic technical writing still needs better source recognition/adjudication, claim-level authoritative grounding, technical relevance/completeness evaluation and educator review. A warning-filled successful export must not be used to claim this goal is finished. Do not proceed to further milestones on the basis of processing tests alone. Final test and artifact results are recorded below.

## Final validation

`env -u PYTHONPATH .venv/bin/python -m pytest -o addopts='' -q`: **325 passed in 28.96 seconds**, including all three real ASR smoke checks. Added tests cover withholding unsupported claims from Word while retaining the original candidate, missing-review fail-closed behavior, editorial chatter/metadata rejection, measurement-unit false positives, preservation of genuine code examples containing greetings, reference validation/code rendering, and filtered API previews/audits.

A fresh local Ollama automatic run completed with the gate enabled; the actual faulty-lecture gate regression withheld 72 of 78 candidate paragraphs with original artifacts unchanged. The separate reference-backed guide has 13 cited official sources and four examples whose exact outputs were executed and checked. DOCX ZIP/readability checks passed. Primary transcript/chunk/manifest/audio hashes and the old generated draft remain unchanged. These results do not replace content-quality acceptance with a software test count.
