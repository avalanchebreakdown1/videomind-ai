# Testing and automated checks

[README](../README.md) · [Setup](SETUP.md) · [CLI](CLI.md)

## Default backend suite

After installing dependencies and FFmpeg, run from the repository root:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest
```

Pytest excludes `real_asr` by default. Tests use controlled ASR/writer responses, generated WAVs, real FFmpeg and local HTTP/SQLite where appropriate. They do not download models, call Ollama or access live YouTube. Local sockets/subprocesses must work; in a restricted coding sandbox request normal execution rather than weakening application transport checks. Dependencies require network access to install, not to run the default suite.

## Frontend and browser integration

From `frontend` after `npm ci`:

```bash
npm test
npm run build
npm run typecheck
PLAYWRIGHT_BROWSERS_PATH="$PWD/../.cache/ms-playwright" node_modules/node/bin/node node_modules/@playwright/test/cli.js install chromium
PLAYWRIGHT_BROWSERS_PATH="$PWD/../.cache/ms-playwright" npm run test:e2e
```

Build first on a fresh clone: the committed `next-env.d.ts` imports Next-generated route types. Chromium installation downloads a browser, not AI weights. On a machine missing browser libraries, use Playwright's documented `install --with-deps chromium` with administrator permission; CI installs these only on its disposable runner. See [Playwright CI setup](https://playwright.dev/docs/ci-intro).

Browser tests start real Next.js/FastAPI servers on **3100/8001**, with controlled ASR/writer/downloader dependencies in `tests/ui_fixture_server.py`. They exercise the proxy, queue, FFmpeg, previews, downloads, recovery, cancellation and errors without external inference. Those ports must be free; fixtures are separate from production ports 3000/8000 and production storage. Test data lives in `/tmp/videomind-ui-integration` unless `VIDEOMIND_UI_TEST_STORAGE` is set. Never use that fixture server to process real user media.

## Optional real-ASR tests

Explicitly prepare speech and checkpoints while online, from the root:

```bash
env -u PYTHONPATH .venv/bin/python scripts/create_sample.py
env -u PYTHONPATH .venv/bin/python -c "from faster_whisper.utils import download_model; download_model('tiny.en', cache_dir='.cache/models'); download_model('small', cache_dir='.cache/models')"
env -u PYTHONPATH .venv/bin/python -m pytest -m real_asr -s
```

The sample generator needs FFmpeg's flite filter and refuses overwrite. These tests are deliberately outside default CI. The real verifier test additionally needs an existing `runs/smoke-final` primary run; see [historical M3 evidence](../MILESTONE_3_REPORT.md). To prepare that run on a fresh clone:

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true .venv/bin/python -m videomind \
  samples/generated/speech.wav --output-dir runs/smoke-final \
  --model tiny.en --language en --chunk-seconds 8 --overlap-seconds 1.5
```

Then run the real-ASR selection again. Preserve existing runs; choose new directories for manual experiments. Tiny speech fixtures validate integration, not accuracy across real lectures. For the single CLI smoke, `VIDEOMIND_TEST_AUDIO` can select another local file, but existing expected phrases are tied to the generated fixture.

## GitHub Actions

[Checks](../.github/workflows/checks.yml) runs on pushes, pull requests and manual dispatch. It uses Ubuntu 22.04, Python 3.10, the dependency lock and Node 24, with pinned action revisions and read-only repository permissions. It installs FFmpeg, Python/frontend dependencies and Chromium, then runs default backend tests, frontend unit tests, the production build/type check and offline browser integration. No secrets, user media, Ollama server or model weights are needed. Failed browser traces/screenshots are retained briefly as CI artifacts.

After pushing, open the repository's **Actions** tab, select **Checks**, and inspect every step. A local pass does not mean GitHub has executed it. Repository settings can disable Actions, and required status checks/branch protection are separate settings; this workflow does not configure them. Implementation follows GitHub's [Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) and [Node](https://docs.github.com/en/actions/tutorials/build-and-test-code/nodejs) workflow guidance.

Green checks do not establish scientific accuracy, word-perfect transcription, all-video accessibility or full lecture coverage. Human-reference accuracy benchmarks and educator review remain necessary. See [repository maintenance validation](REPOSITORY_CHECKS.md) for the checks actually executed for this workflow/documentation change.
