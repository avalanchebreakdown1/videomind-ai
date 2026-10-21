# Fresh installation

[README](../README.md) · [Testing](TESTING.md) · [CLI](CLI.md)

These commands target Ubuntu/Linux and CPU inference. Recorded application runs used Ubuntu 22.04 and Python 3.10. Other operating systems, CUDA setups and Python versions have not received the same end-to-end validation.

## Prerequisites

You need Git, Python 3.10 with venv/pip, FFmpeg/ffprobe, an existing Node/npm installation to run `npm ci`, and local Ollama for document writing. Check:

```bash
git --version
python3 --version
ffmpeg -version
ffprobe -version
node --version
npm --version
ollama --version
```

On Ubuntu, if system packages are missing, install them yourself with administrator permission:

```bash
sudo apt-get update
sudo apt-get install git python3-venv python3-pip ffmpeg
```

Those commands do not install Node or Ollama. Use the official [Node installation instructions](https://nodejs.org/en/download) and [Ollama Linux instructions](https://docs.ollama.com/linux). Use Node 24 for a new setup, as CI does. The frontend also pins a project-local Node 24.22.0 in development dependencies; npm scripts use it without replacing system Node. The existing developer machine bootstrapped installation with Node 18/npm 10, but older Node versions emit dependency engine warnings during installation.

Models consume several GB of disk and inference memory; performance depends on hardware/source duration. Normalized audio alone adds roughly 115 MB per hour, alongside source media, model caches and outputs. There is no automatic storage quota.

## Clone and install Python dependencies

Use a new parent folder, without cloning inside an existing VideoMind checkout:

```bash
git clone https://github.com/avalanchebreakdown1/videomind-ai.git
cd videomind-ai
python3 -m venv .venv
env -u PYTHONPATH .venv/bin/python -m pip install --upgrade pip
env -u PYTHONPATH .venv/bin/python -m pip install -r requirements.lock
env -u PYTHONPATH .venv/bin/python -m pip install --no-deps -e '.[dev]'
env -u PYTHONPATH .venv/bin/python -m pip check
```

The lock records the Python 3.10 dependency set; `pyproject.toml` declares supported ranges. Dependency updates should be tested separately. Clearing `PYTHONPATH` isolates inherited ROS packages for that command without changing your shell or ROS installation. Do not copy another checkout's `.venv`.

## Install and build the frontend

From the repository root:

```bash
cd frontend
npm ci
npm run build
npm run typecheck
cd ..
```

Keep development dependencies installed: the local Node runtime and build/test tools live there. Build before standalone type checking on a fresh checkout so Next.js route type definitions exist.

## Explicitly prepare models

The launcher uses offline ASR by default. Download its `small` checkpoint once while online, from the repository root:

```bash
env -u PYTHONPATH .venv/bin/python -c "from faster_whisper.utils import download_model; download_model('small', cache_dir='.cache/models')"
```

Faster-Whisper uses converted CTranslate2 checkpoints, not original Whisper `.pt` files. See [model download documentation](https://github.com/SYSTRAN/faster-whisper#model-download).

If Ollama is not already serving, open another terminal and leave this running:

```bash
ollama serve
```

If Ollama is already running as a service, use that instance. In the project terminal:

```bash
ollama pull qwen2.5-coder:7b
ollama list
curl --fail http://127.0.0.1:11434/api/tags
```

These are explicit model downloads. Select the installed local model, not a cloud model; no Ollama API key is needed for local inference. The app does not pull Ollama models automatically. The model names reproduce launcher defaults, not a guarantee of factual accuracy. Export `VIDEOMIND_WRITE_MODEL` to select another installed model.

## Start the application

From the repository root:

```bash
env -u PYTHONPATH .venv/bin/python scripts/start_local.py
```

Open http://127.0.0.1:3000. Backend documentation is at http://127.0.0.1:8000/docs. From another terminal:

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
```

Health reports worker availability/limits; it does not load/check models or prove a full processing run. Test a short authorized audio file, inspect transcript/notes and download DOCX/TXT. Notes require factual review even when processing succeeds.

Ctrl+C in the launcher's terminal stops its frontend/backend children, not your separate Ollama server. Ports 3000 and 8000 must be free. Use only one API worker per storage folder.

## Settings and troubleshooting

The backend reads environment variables, **not** a root `.env` automatically. Inspect [`.env.example`](../.env.example), then export intended overrides:

```bash
export VIDEOMIND_MODEL=small
export VIDEOMIND_LOCAL_FILES_ONLY=true
export VIDEOMIND_WRITE_MODEL=qwen2.5-coder:7b
```

Do not blindly source `.env.example` as launcher settings: its general CLI defaults include `MODEL=base` and online first-use downloads. The launcher defaults to `small` and offline loading unless overridden. Next.js can read private `frontend/.env.local`; server-only `VIDEOMIND_API_URL` must remain loopback. Keep both servers bound to loopback.

| Symptom | Check |
|---|---|
| Offline ASR/model error | Cache the selected checkpoint under `.cache/models` from the same root, or set an absolute `VIDEOMIND_MODEL_DIR`. |
| Ollama connection/model error | Check `/api/tags`, `ollama list`, the server and `VIDEOMIND_WRITE_MODEL`. |
| Missing FFmpeg/ffprobe | Both commands must be on PATH. |
| Missing `.next/BUILD_ID` | Run `npm ci` and `npm run build` in `frontend`. |
| Occupied port/worker lock | Stop your earlier launcher gracefully; do not delete live storage/locks. |
| Restricted YouTube source | Use an authorized upload; do not bypass restrictions or import credentials. |
| Document CLI exit 2 | A reviewable draft was generated; inspect outputs/audit. Exit 1 is processing failure. |

Source media, transcripts, model calls and outputs remain in local ignored folders. Model preparation and YouTube ingestion use network access; writing calls local Ollama. Do not publish private artifacts or put GitHub tokens in configuration templates.
