# Evaluating VideoMind

VideoMind has software regression tests and an offline content evaluation suite.
It does not yet have evidence establishing production readiness. In particular,
real lecture content acceptance, recovery under failures and sustained resource
use remain open. The service currently targets a local single user.

## Run the suite

```bash
env -u PYTHONPATH .venv/bin/python -m videomind evaluate \
  --suite tests/fixtures/benchmark/suite.json \
  --output /tmp/videomind-evaluation-001.json
```

Choose a new output filename each time. Exit codes: **0** content gate passed,
**2** failed or incomplete evidence, **1** invalid inputs or I/O failure.
Reports and all inputs must be separate; existing reports are never overwritten.
The command reads local files only, without inference, downloads or network use.

The committed suite deliberately fails: strict WER is 3/29 (10.34%), only 2/6
critical phrases survive, the reference is synthetic, and notes lack review.
This exercises the gate; it is not a measurement of a production model.

## Make a private real suite

Follow [the benchmark reference/review contract](BENCHMARK.md) to prepare permitted
excerpts, human-listened transcripts and hash-bound notes annotations. Copy the
suite JSON into the private evaluation directory. Paths resolve relative to that
manifest; absolute local paths also work. Keep private samples/reports out of Git.
Each sample supplies `reference`, `transcript`, `notes`, optional `review`, and
`slices`. References must have unique sample IDs and distinct reference file hashes.

The policy explicitly sets:

| Field | Meaning |
|---|---|
| `max_wer` | Maximum strict WER for every excerpt; lower is better |
| `min_critical_recall` | Minimum literal phrase fraction for every excerpt |
| `max_missing` | Maximum reviewer-identified omitted concepts per excerpt |
| `max_distorted` | Maximum reviewer-identified distorted concepts per excerpt |
| `max_unsupported_additions` | Maximum reviewer-identified unsupported additions per excerpt |
| `min_reviewed_sources` | Minimum distinct media SHA-256 declarations with reviewed references and notes |
| `required_slices` | Coverage labels that must occur on samples with both reviews |

The example's 10% WER, 100% critical phrase retention, zero content findings and
three sources are **illustrative thresholds**, not validated acceptance standards.
Set and version the policy before tuning a candidate. Use a held-out set for
acceptance so repeatedly fixing development examples does not masquerade as
generalization. Choose slices that represent actual intended use: subject,
accent, noise, recording length, input format and chunk-boundary conditions.
A label alone does not prove the condition was exercised; maintain a reviewer
audit identifying media ranges, actual run configuration and model digests.

Every sample is gated separately; averages cannot hide a bad excerpt. Synthetic
references and missing reviews cannot satisfy reviewed coverage. Multiple excerpts
from one source count as one source. Failed metrics take precedence over missing
evidence in the top-level status, but both remain in the report. A passed content
gate always retains `production_readiness: not_assessed`.

The report includes the exact policy, manifest hash, source/candidate/review hashes,
per-sample measurements, review annotations, failures and missing evidence. It
recomputes benchmark results from source artifacts, rather than trusting imported
score summaries. Reviewer identity, media hashes and slice labels are declarations;
software cannot authenticate their truth. Literal phrase presence is not semantic
recall. Source-consistency review is not external scientific fact verification.

## Evidence still needed for production acceptance

| Layer | Evidence to collect | Current position |
|---|---|---|
| Software | Backend tests; frontend checks/build; offline browser flows | Existing automation; fixtures isolate models/network |
| Real pipeline | Permitted media through ingestion, real ASR, Ollama, DOCX/TXT and browser downloads | Opt-in real browser tests exist; not run by this content suite |
| Transcript | Reviewed WER; terms, numbers, units, negations and boundary inspection | Benchmark supported; real reference acceptance remains open |
| Notes | Coverage, omissions, distortions, additions; educator inspection; authoritative factual checks where needed | Hash-bound source-consistency annotations supported; factual review remains separate |
| Reliability | Process restart, Ollama timeout/unavailable, interrupted uploads, cancellation, corrupt input and disk-full behavior | Recovery and hard inference timeout gaps remain documented in ISSUES.md |
| Sustained operation | Successful/failed job counts, queue delays, p50/p95 duration, peak memory and disk growth over a specified workload | No soak-test acceptance evidence yet |
| Deployment | Intended users, access controls, isolation, quotas and supported exposure | Loopback/single-user controls; public multi-user hosting is not implemented |

For an all-day evaluation, first define a fixed permitted job queue, maximum job
count, time/storage limits and stop conditions. Run a bounded 24-hour soak with
periodic health/resource measurements, then inspect every failure and representative
documents. A live terminal or Telegram notification does not establish recovery or
quality. Fix known watchdog/quota gaps before unattended production workloads.

## Remote control through Telegram

A separate local bridge could receive Telegram prompts, send progress and expose
Approve/Deny buttons. Codex development control would use a client built around
Codex App Server's prompt/event/approval protocol. VideoMind job control would call
its existing local job API. Neither bridge is implemented by this evaluation work.

Keep VideoMind bound to loopback; a bot can poll Telegram over outbound HTTPS.
Restrict commands and callbacks to an allowed Telegram user/chat, bind approvals to
an exact pending action with expiry and one-time use, and retain an audit. A denied
or expired action stays denied. Host-managed permission controls still apply;
Telegram is not authority to bypass them. Never forward arbitrary bot text to a
shell. Tokens belong in local secret/environment configuration, not Git or chat.
The machine must remain awake, online and running the bridge/worker; supervision,
bounded queues and restart handling are separate implementation work.

Protocol sources: [Telegram Bot API](https://core.telegram.org/bots/api) and
[Codex App Server](https://learn.chatgpt.com/docs/app-server).
