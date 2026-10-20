# Milestone 1 report

Date: 2026-10-19 (Asia/Tokyo). Status: implemented and passed local acceptance checks. Milestone 2 has not started.

## Environment inspection

- Ubuntu 22.04.5 LTS, Python 3.10.12, FFmpeg/ffprobe 4.4.2.
- Workspace initially contained no project source. The exposed `.git` directory was not a usable Git repository; no commits or Git changes were attempted.
- Faster-Whisper was initially absent. Created `.venv`, installed dependencies with approved network access, and cached `tiny.en` under `.cache/models`. No system packages or configuration were changed.
- Inherited ROS `PYTHONPATH` initially caused pytest plugin import failures. Running project commands through `env -u PYTHONPATH` isolates those unrelated packages. Dependency check now reports no broken requirements.

## Files created

- Documentation: `README.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, `API_DESIGN.md`, `DEVELOPMENT_PLAN.md`, `AGENTS.md`, and this report.
- Packaging/configuration: `pyproject.toml`, `requirements.lock`, `.env.example`, `.gitignore`.
- Application: `backend/videomind/{__init__,__main__,cli,config,models,pipeline}.py`.
- Services: `backend/videomind/services/{__init__,audio_service,chunking_service,transcription_service,stitching_service,document_service}.py`.
- Tests: `tests/{conftest,test_chunking,test_stitching,test_audio_pipeline,test_transcriber,test_real_asr}.py`.
- Local fixture tool: `scripts/create_sample.py`; generated speech and reference text under `samples/generated/` (ignored artifacts).
- Retained real-run artifacts: `runs/smoke/` and `runs/smoke-final/` (ignored artifacts).

## Implemented behavior

The CLI accepts a local file, validates/probes audio and streams normalized mono 16 kHz PCM to disk. It plans ordered 300-second core chunks with up to 2 seconds of context on either side and extracts/inferences one bounded chunk at a time. The default engine is Faster-Whisper, CPU/int8. Language, model, limits and retries are configurable.

Each successful chunk retains original segments and word timestamps/probabilities. Timestamp ownership stitches the raw transcript without text-based deletion of real repetitions. Atomic UTF-8 TXT and timestamped JSON outputs accompany a progress/state manifest. New output directories are required. Bounded inference retries, invalid-media failures and interruption preserve failed state and completed raw chunk evidence. Normalized audio remains available; temporary chunk WAVs are removed unless retained explicitly.

## Executed checks and results

| Check | Command or evidence | Result |
|---|---|---|
| Offline unit + FFmpeg integration suite | `env -u PYTHONPATH .venv/bin/python -m pytest` | **78 passed**, 1 opt-in test deselected; 2.79 seconds on final run |
| Real local speech through CLI/Faster-Whisper | `env -u PYTHONPATH VIDEOMIND_TEST_OUTPUT=runs/smoke-final .venv/bin/python -m pytest -m real_asr -s` | **1 passed**, 78 deselected; 1.67 seconds; no warnings |
| Editable package install | `env -u PYTHONPATH .venv/bin/python -m pip install --no-build-isolation --no-deps -e .` | Passed after installing project-local build tools |
| Installed console entry point | `env -u PYTHONPATH .venv/bin/videomind --help` | Passed |
| Dependency consistency | `env -u PYTHONPATH .venv/bin/python -m pip check` | No broken requirements found |
| Speech reference comparison | Lowercase word-token comparison of `samples/generated/expected.txt` and `runs/smoke-final/raw_transcript.txt` | All **38 words** match in order; punctuation differs |

Test coverage includes five-hour chunk planning, exact core endpoints, invalid/nonfinite configuration, real resampling and chunk lengths, sample-content checks at seek offsets, transcript ordering, overlap ownership, legitimate repeated words, Unicode export, the complete state-transition matrix, retries, permanent failure, corrupt media, missing input/tools, subprocess timeout, overwrite prevention, empty recognition warnings, and partial-evidence preservation on interruption. Default tests use mock ASR and do not request models or network access.

Real ASR test details: FFmpeg flite synthesized **14.815 seconds** of local English speech. `tiny.en` ran on CPU/int8 using **two 8-second cores with 1.5-second context** to exercise stitching. Manifest reports `completed`, 100%, 2/2 chunks, and `audio_verified: false`. Both original chunk JSON files are present. The final transcript is:

> Welcome to Video Mind. Today we will learn how solar panels produce electricity, solar panels convert sunlight into electrical energy, this energy can power lights and charge batteries, the recording ends with the words thank you for listening.

Tested versions include Faster-Whisper 1.2.1, CTranslate2 4.8.3, PyAV 17.1.0 and pytest 9.1.1. Exact transitive versions are in `requirements.lock`. The cached model snapshot is `0d3d19a32d3338f10357c0889762bd8d64bbdeba` from Systran/faster-whisper-tiny.en.

The first test run found two incorrect assertions assuming full overlap even at a clipped final boundary; they were corrected. Real ASR initially emitted deprecated serialization warnings; the adapter now uses dataclass serialization for current models while supporting older named-tuple outputs. Final tests pass without warnings.

## Known limitations

- This is **raw ASR**, not an independently audio-verified transcript. No second model/pass has been run. Timestamp ownership can still miss or repeat speech if models disagree at chunk boundaries; preserved outputs enable future review.
- Synthetic speech with 38 words proves local integration only. Real long recordings, noise, accents, multilingual speech and speaker changes have not been accuracy-benchmarked. Five-hour coverage is tested as a chunk plan, not a five-hour inference run.
- No web UI, FastAPI endpoints, background worker, SQLite jobs, YouTube ingestion/URL validator, independent verification, Ollama writing or DOCX export yet. Corresponding later-milestone tests are intentionally deferred.
- CPU inference is tested. GPU setup/performance, model quality beyond this fixture, restart/resume and cancellation APIs are not implemented or tested.
- Normalized audio and model cache consume disk. No enforced storage/duration quota; trusted single-user local files only. Subprocesses have timeouts, but inference has no hard watchdog. Empty ASR output is flagged and never filled with invented content.
- Default model is `base`; only `tiny.en` weights were downloaded for acceptance. Select `--model tiny.en` for the cached smoke model, or download another model on first use.

## Next milestone

Milestone 2 is ingestion and the web application: strict authorized YouTube retrieval and bounded uploads, SQLite/local worker with nonblocking FastAPI jobs and cancellation, and the Next.js/React/Tailwind interface. Its detailed acceptance gates are documented in `DEVELOPMENT_PLAN.md`. No Milestone 2 work was begun.
