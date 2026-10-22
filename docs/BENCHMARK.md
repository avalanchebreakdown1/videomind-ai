# Offline accuracy benchmark

For multi-sample policy gates, coverage requirements and a production-evidence
checklist, see [Evaluations](EVALUATIONS.md). The single-sample command below keeps
its existing exit-code and `not_assessed` acceptance semantics.

The first integration batch adds evaluation tooling, not a claim of accurate lecture
transcription or educational content. It reads existing UTF-8 text files; it never
runs ASR, Ollama, M3 verification or network requests. The existing CI backend test
step automatically runs its regression tests.

## Run the controlled example

From the repository root, choose a new report filename:

```bash
env -u PYTHONPATH .venv/bin/python -m videomind benchmark \
  --reference tests/fixtures/benchmark/reference.json \
  --transcript tests/fixtures/benchmark/transcript.txt \
  --notes tests/fixtures/benchmark/notes.txt \
  --output /tmp/videomind-benchmark-001.json
```

The bundled example is original synthetic text with deliberate errors. It contains
no user media, actual model output or human-reviewed lecture. The boundary example
checks phrase retention only; it does not exercise timestamp stitching.

The report records reference/candidate SHA-256 hashes, evaluator/schema versions,
edit distance, strict word error rate (WER), individual critical phrase checks and
notes-review status. It refuses to overwrite a report or write over an input.
Exit 0 means evaluation completed, not that the content passed. Invalid inputs,
stale annotations and existing output paths return 1. Accuracy acceptance is always
`not_assessed`; no numerical acceptance thresholds have been approved yet.

WER is Levenshtein distance divided by reference word count. Tokens split on
whitespace only; case, leading decimals, subscripts/superscripts, minus signs and
punctuation remain significant. This is deliberately stricter than normalized WER
and should not be compared directly to scores using other normalization rules.
Insertions can produce WER above 1. Alignment uses rolling rows and is bounded to
4000 tokens per text and four million alignment cells; use representative excerpts
instead of passing an entire lecture. Phrase checks are case-sensitive substring
checks, not semantic judgments: a phrase may occur in the wrong context, and a valid
paraphrase may fail. They must not be interpreted as verified accuracy or recall.

## Prepare a real reference

1. Select a permitted short lecture excerpt (a few minutes). Record the media hash,
   source identity, start/end times and permission basis in private evaluation notes.
2. Have a named reviewer listen and prepare a faithful reference transcript without
   silently repairing disputed speech. Represent unresolved audio explicitly in the
   review notes; use only adjudicated portions for numerical comparison.
3. Copy the reference JSON structure to a private directory outside committed
   fixtures. Set `reference_status` to `human_reviewed`, record `reviewed_by` and the
   actual media `source_sha256`, and confirm permission. `source_description` should
   identify the excerpt/time range. These fields are reviewer declarations; the
   evaluator does not open media or authenticate a reviewer.
4. Define unique critical-check IDs for terms, numbers, negations, examples and
   qualifications near chunk boundaries. Each phrase must occur in the reference.
   Define unique concept IDs and descriptions for the notes review.
5. Pass the matching candidate excerpt and notes TXT to the command. Compare raw
   transcription separately from editorial corrections; never substitute rewritten
   notes for the candidate transcript. Preserve the original run and model-call
   provenance; retain a private mapping from these candidate hashes to that run.

Do not commit private media, reference transcripts, candidate outputs or reports.
The fixture format is illustrated by `tests/fixtures/benchmark/reference.json`;
unknown JSON fields, duplicate IDs and unconfirmed permission are rejected.

## Review notes separately

Without `--review`, omission/distortion/addition counts are `null` and status is
`unchecked`, even for empty notes. The evaluator never fabricates semantic scores.

A human reviewer should inspect the entire candidate notes excerpt against the
reference and complete this JSON contract (replace placeholders):

```json
{
  "reviewer": "Reviewer name",
  "reference_sha256": "64 lowercase hex characters from report.hashes",
  "notes_sha256": "64 lowercase hex characters from report.hashes",
  "complete": true,
  "assessments": [
    {
      "concept_id": "ID from reference.concepts",
      "verdict": "covered",
      "quote": "Exact supporting passage in candidate notes",
      "reason": "Why this preserves the reference concept and qualifications"
    }
  ],
  "unsupported_additions": [
    {
      "quote": "Exact candidate passage unsupported by the reference",
      "reason": "Explain what was added and why the reference does not support it"
    }
  ]
}
```

Assess every concept exactly once as `covered`, `distorted` or `missing`. For
`missing`, use an empty quote; for other verdicts, quote the candidate verbatim.
Use an empty additions array only after inspecting the entire excerpt. Rerun with
`--review /private/path/review.json` and a new output filename. Hashes bind the
annotations to the exact reference and notes bytes, rejecting stale reviews.
The report retains the annotations and their hash for audit. Complete human review
is a declaration, not something software can prove. Counts summarize those supplied
judgments; they are not automatic factual checks. External factual review, if done,
must have its own authoritative references and audit.

## Controlled baseline and next gate

The synthetic regression has 29 reference words, three edits and WER
`3 / 29 = 0.10344827586206896`. Only two of six critical phrases remain present.
The notes are unchecked in the command above. Controlled test annotations exercise
two covered concepts, one distortion, one omission and one unsupported date; these
annotations are test code, not educator acceptance.

No real lecture accuracy baseline has been established in this batch. The next gate
is a permitted excerpt and human reviewer, followed by recorded measurements and
agreed accuracy thresholds. Add varied subjects, accents/noise and longer boundary
cases before generalizing results. Do not close M1–M4 quality issues from this
synthetic baseline. Recovery/readiness and other feature batches remain separate.

## Integration checks executed — 2026-10-21

- Default backend suite: **377 passed, 3 real-ASR tests deselected**, including
  **23 benchmark tests**. The original sandbox run stalled in local API tests and
  was interrupted; the complete run passed with normal local-socket permissions.
- Frontend unit checks: **2 passed**. Production build and subsequent type check
  passed. The initial sandbox build failed with `Could not parse output from
  TypeScript's --showConfig.`; the same build passed outside the sandbox without
  changing application code.
- Existing offline Chromium integration: **7 passed**, covering upload/URL jobs,
  downloads, error handling, cancellation, recovery and mobile layout.
- The documented benchmark command executed successfully and its controlled
  results matched the baseline above. The report remains outside Git in `/tmp`.
- No audio/inference integration was changed, so real-ASR smoke was not rerun.
  No models were downloaded or live inference invoked. Production transcript,
  evidence and model outputs were not edited.

These are local software checks. Remote CI execution and real lecture content
acceptance are separate results.
