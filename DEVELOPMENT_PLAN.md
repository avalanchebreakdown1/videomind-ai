# Implementation roadmap

Current authorization includes transcription, ingestion, optional audio verification, direct rewriting, DOCX export and the Next.js frontend. Preserve historical media/transcripts/runs; passing software checks does not close accuracy or educational-quality acceptance.

## Implemented baseline

| Area | Current behavior | Evidence |
|---|---|---|
| M1: audio transcription | Streamed FFmpeg normalization, bounded Faster-Whisper chunks, raw evidence and versioned stitching | [M1](MILESTONE_1_REPORT.md), [stitching fixes](FIXES_M1_M3.md) |
| M2: ingestion/jobs | Guarded YouTube audio and uploads, FastAPI, SQLite, one worker, progress and cooperative cancellation | [M2](MILESTONE_2_REPORT.md) |
| M3: optional verification | Distinct ASR checkpoint, selected source-audio checks, disagreements/uncertainty and separate evidence | [M3](MILESTONE_3_REPORT.md) |
| M4/M5: direct notes/export | One installed Ollama model, bounded transcript chunks, attribution, editorial audit and DOCX/TXT | [Direct rewrite](DIRECT_REWRITE_ACCEPTANCE.md) |
| Frontend | Responsive URL/upload workflow, previews/downloads, errors, cancellation and job reopening via bounded loopback proxy | [Integration](FRONTEND_INTEGRATION_REPORT.md) |

M3 is off by default. Writing never implicitly enables it. The old extraction/outline/review workflow is retained only as `--pipeline legacy`; see [compatibility guide](docs/LEGACY_PIPELINE.md). Historical reports describe the scope/results at their original milestone, not current feature availability.

## Repository maintenance

- Keep the README focused on current behavior, with fresh-install, CLI and testing guides.
- Run controlled backend/frontend/browser checks through [GitHub Actions](.github/workflows/checks.yml), without model/media downloads in tests.
- Preserve private artifacts outside Git; keep source/model provenance and correction/exclusion audits for generated outputs.
- Commit focused, tested improvements and report the push result. CI status must be checked on GitHub after upload.

## Next reliability and quality work

1. Use the [offline benchmark tooling](docs/BENCHMARK.md) to establish a small human-reviewed transcript and document baseline covering technical terms, numbers, examples, qualifications and omissions. Synthetic evaluator tests are implemented; real lecture review and acceptance thresholds remain pending.
2. Add explicit model-readiness diagnostics; the existing health route only checks worker/configuration availability.
3. Design resumable processing, hard inference timeouts and recovery without mutating old evidence.
4. Add storage/retention quotas and better resource admission for long jobs.
5. Expand representative authorized-source testing and measure CPU inference performance.

These items remain planned; see [known issues](ISSUES.md). Public hosting, authentication/multi-user isolation, GPU validation and visual extraction require separate implementation. Before publication, technical documents still require factual review.
