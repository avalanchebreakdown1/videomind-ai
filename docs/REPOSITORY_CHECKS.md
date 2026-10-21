# Repository maintenance validation — 2026-10-21

This change updates current documentation and adds automated software checks. It does not change audio/inference behavior or historical transcripts, generated outputs or acceptance reports.

## Changes

- README now describes the implemented frontend and direct rewriting, with explicit limitations.
- Setup, CLI, testing and legacy compatibility have separate guides. Examples explain that private historical runs are absent from a clone.
- Architecture, API, requirements, roadmap and issue tracking distinguish current functionality from legacy findings/planned work.
- GitHub Actions defines backend, frontend, build, type and offline browser checks, with pinned action revisions, read-only repository access and bounded job/artifact lifetimes.

## Executed checks

The source baseline was exported to a new temporary folder. A fresh Python virtual environment and fresh frontend dependencies were installed from the committed locks, without reusing `.venv`, `node_modules` or `.next` from the working application.

| Check | Result |
|---|---|
| Default backend suite, working checkout | 354 passed; 3 optional real-ASR tests deselected |
| Python lock + editable package install, clean copy | Passed; `pip check` found no broken requirements |
| Default backend suite, clean copy with offline model settings | 354 passed; 3 real-ASR tests deselected |
| Frontend `npm ci` and unit tests, clean copy | Installed successfully; 5 tests passed |
| Production build and type check, clean copy | Passed, including generation of route types |
| Chromium integration, clean copy | 7 tests passed using isolated fixture storage/ports |
| CLI help: transcription, document, verify, restitch | Passed |
| Workflow YAML structure, action pins and local documentation links | Passed |

The clean installation used Python 3.10 and the existing Node 18/npm 10 bootstrap; application npm scripts ran the pinned local Node 24.22.0. Node 18 emitted dependency engine warnings during installation; use Node 24 for new setups, as CI does. Chromium was reused from the existing browser cache; models and user media were not copied/downloaded. Browser OS dependencies were already installed. No system-wide packages were changed.

The commands in the workflow were exercised locally as described above; the complete GitHub-hosted runner job has not been observed as part of this local validation. After upload, inspect the repository's Actions tab. GitHub settings/authentication and OS dependency provisioning remain distinct from local checks.

## Limitations and next work

No new real-ASR/YouTube/Ollama run was needed for documentation/CI changes. These results do not establish word-perfect recognition, scientific truth or complete lecture coverage. Model readiness diagnostics, reference-based quality evaluation, resumable jobs and storage controls remain planned in [the roadmap](../DEVELOPMENT_PLAN.md).
