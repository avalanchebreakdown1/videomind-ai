# Focused local acceptance — 22 October 2026

Scope: note omissions, technical distortions and recurring generation failures;
real end-to-end testing and a 24-hour soak. Other roadmap work remains deferred.

## Implemented safeguards

- Direct single-model rewriting retains separate immutable source/model artifacts.
  Retries receive editorial feedback outside transcript data. At most three
  attempts run per passage; final recovery excludes the rejected assistant response.
- Narrow coverage checks reject missing quantitative examples, invented numbers,
  changed physical units and percentage/count substitutions. Scientific notation
  and equivalent decimal spellings are supported; unit case remains significant.
- Correction quotes require actual source excerpts. Unique case/spacing matches
  restore the exact excerpt and record both spellings; fabricated or ambiguous
  matches fail. Candidate responses remain unchanged in model-call evidence.
- Common presenter narration and generic editorial headings trigger regeneration.
  Clear nontechnical commercial offers are excluded from reading outputs with
  their full text and source IDs retained in the exclusion audit.
- CLI/API and launcher settings agree on cached `small` ASR with offline loading;
  the writer defaults to the installed `llama3.1:8b` model. Explicit overrides remain.

These checks do not establish semantic completeness, correct relationships, or
factual accuracy. Raw ASR mistakes can survive into notes. Human review is still
required before publishing educational material.

## Executed checks

| Check | Observed result |
|---|---|
| Default offline Python suite | 423 passed; 3 real tests deselected |
| Cached `tiny.en` ASR integration smoke | 1 passed |
| Frontend unit checks and TypeScript | Passed |
| Separate offline browser fixtures | 7 passed |
| Real production browser, authorized 180-second recording | Passed in 48 seconds |

The real browser test used live local FastAPI, Next.js, cached `small` ASR and
Ollama rather than fixture responses. It covered audio upload, automatic writing,
notes preview, Word/notes TXT/transcript TXT downloads, and reload recovery.
Evidence is retained locally in `runs/focused-browser-03` and job
`aa869936-42a8-4799-a0c2-03b30c99b68e` in `runs/focused-real-server-03`.
The test does not establish YouTube ingestion reliability or content accuracy.

## Acceptance still open

- Full 62.8-minute lecture rewriting remains unaccepted. Several preserved runs
  failed on narration, malformed correction quotes or omitted Java-version
  details (`1.8`/`1.9`). The latest 3,500-character trial was withheld correctly;
  a separate 1,500-character trial recovered that discussion but failed at 67%
  on another invented correction quote. Both trials retained evidence and
  withheld final exports. Neither establishes full-lecture acceptance.
- Inspection of an earlier completed short draft found an incorrect revenue
  attribution, an unrepaired garbled tool name, repeated topics and advertising.
  The advertising cleanup has a regression test; these observations are not
  evidence that every remaining distortion has been fixed.
- Inspection of the latest real browser's actual Word download confirmed both
  traffic values survived, but also exposed the raw-ASR value `2626` as an
  authority score and an unsupported explanation of its calculation. This is a
  concrete content-quality failure despite the successful browser workflow;
  neither numeric presence checks nor the soak independently resolve it.
- The 24-hour soak started at **2026-10-22 12:28 UTC** against the frozen local
  candidate. Its first real cycle passed. Completion is not yet established.
  Inspect `runs/focused-soak-24h-01/report.json` for recorded cycles, hashes and
  final state; a running report is not a pass. Expected end is 23 October at
  approximately 12:28 UTC, provided the machine and services stay running.

Any code change requires a new soak against freshly restarted services. Preserve
all old runs. The next acceptance step is to inspect the entire resulting lecture
document and resolve remaining content failures, then obtain a completed soak on
the final candidate; do not advance to deferred milestones on software checks alone.
