# CLI workflows

[README](../README.md) · [Setup](SETUP.md) · [Testing](TESTING.md)

Run from the repository root after setup. Supply your own authorized media and use a **new output directory for every attempt**. Earlier lecture runs are not included in a clone.

## Local audio to raw transcript

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind /absolute/path/to/audio.mp3 \
  --output-dir runs/local-01 --model small --language en
```

Omit `--language en` for automatic detection. CPU/int8, four threads, 300-second cores and two-second context are defaults. Only bounded audio chunks enter ASR memory. The selected checkpoint must be cached for offline use.

## YouTube to raw transcript

```bash
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind \
  --youtube-url 'https://www.youtube.com/watch?v=VIDEO_ID_HERE' \
  --authorized --model small --output-dir runs/youtube-01
```

Replace the URL with a single accessible video you are authorized to process. Quote URLs so shell `&` characters cannot split commands. Playlists/live streams and arbitrary hosts are rejected. `--authorized` records your confirmation, not a determination of permission. Failed downloads retain diagnostics; uploads are the fallback.

YouTube output includes `ingestion.json`, sanitized `download/metadata.json`, `download/source.audio` and `transcription/`. Local-file runs write transcription artifacts directly into their output directory.

## Transcript to technical notes and DOCX

```bash
env -u PYTHONPATH .venv/bin/python -m videomind document \
  --source-dir runs/youtube-01/transcription \
  --output-dir runs/youtube-01/document-01 \
  --model llama3.1:8b \
  --source-title 'Your educational video title' \
  --source-url 'https://www.youtube.com/watch?v=VIDEO_ID_HERE'
```

For the local-file example use `--source-dir runs/local-01`. One installed Ollama model rewrites bounded transcript chunks, retains technical explanations/examples, removes chatter and uses context for editorial completions. The instructions request detailed subject notes, including mechanisms, conditions and examples, with creator credit in attribution rather than presenter narration. Reported demonstrations must retain their scope and limitations. Default source chunks are 3,500 characters and the generation ceiling is 4,096 tokens; this is a ceiling, not a promised output length. It does not independently verify facts. Raw transcripts remain unchanged; normal notes have no inline uncertainty markers.

Outputs include DOCX/TXT/JSON, source chunks/hashes, model calls, `rewrite_audit.json`, `coverage.json`, `quality.json` and a manifest. Common presenter-narration patterns and numeric omissions trigger up to three attempts per passage; the final recovery starts without replaying the rejected candidate and retains prior validation feedback. Persistent detections withhold the export and retain responses and audit evidence. These narrow checks do not establish complete coverage or factual accuracy. Unique correction quotes with case/spacing differences are restored to the exact source excerpt with an audit; ambiguous or invented quotes are rejected. Failed integrity/schema checks also withhold final documents but retain diagnostics. Every source character is submitted; complete topic retention requires human evaluation.

`coverage.json` records contiguous source spans and whether the complete transcript was submitted; it explicitly does not certify semantic completeness. Deterministic checks flag selected missing comparisons/measurements, unit changes, novel numerical claims, invented URLs and nonliteral correction quotes. A unique case-only quote match can be restored to exact source spelling, with both versions audited and raw model responses retained. Retry feedback is a separate conversation message, not appended to source data. Plain prose incorrectly emitted as code is excluded with an audit. These checks can miss errors or reject a valid paraphrase; a failed real-model trial is not an accepted document.

If export fails after producing reading files, those files are retained in a fresh `withheld-exports-*` directory with hashes in the failed manifest. They are not delivered as normal documents. See [unattended development boundaries](UNATTENDED_WORK.md).

The document CLI exits **2** for an unreviewed generated draft, **1** for failure and **130** for interruption. Successful raw transcription exits **0**. Document exit 2 is not a failed download.

## Optional audio verification

This extra pass is off in the normal workflow and can be slow. It needs a distinct checkpoint. If primary ASR used `small`, explicitly prepare another such as `base`:

```bash
env -u PYTHONPATH .venv/bin/python -c "from faster_whisper.utils import download_model; download_model('base', cache_dir='.cache/models')"
env -u PYTHONPATH VIDEOMIND_LOCAL_FILES_ONLY=true \
  .venv/bin/python -m videomind verify \
  --run-dir runs/youtube-01/transcription \
  --output-dir runs/youtube-01/review-01 --model base
```

The source needs its original raw artifacts and `normalized.wav`. Selected audio is decoded without primary text prompts. Separate evidence preserves candidates, disagreements, coverage, hashes and uncertainty. Original words are never replaced. Whisper-family checkpoints can share errors; agreement/full time coverage do not prove correctness. Optional reviewed transcript TXT can contain uncertainty annotations; default written notes do not.

## Historical stitching rebuild

```bash
env -u PYTHONPATH .venv/bin/python -m videomind restitch \
  --run-dir runs/youtube-01/transcription --output-dir runs/rebuilt-01
```

Rebuilds reuse saved primary chunks without new inference; sources remain unchanged. Old runs validate under their recorded version. New runs use bounded, one-to-one `overlap_alignment_v2`, retaining boundary alternatives and ambiguity. Rebuilding is not independent audio verification.

## Raw artifacts and API

| Artifact | Contents |
|---|---|
| `raw_transcript.txt` / `.json` | Primary speech; JSON includes word times/probabilities |
| `raw_chunks/` | Original ASR segments and timestamps |
| `chunks.json` | Core/overlap plan |
| `manifest.json` | Settings, progress, warnings/failure state |
| `stitching.json` | Boundary candidates and decisions |
| `normalized.wav` | Retained mono 16 kHz PCM |
| `audio_chunks/` | Temporary WAVs; retain with `--keep-chunks` |

See [API design](../API_DESIGN.md) for uploads/URLs, polling, cancellation, formats and errors. Use one worker on loopback. The former extraction/outline/review workflow is explicitly available through `document --pipeline legacy`; see [legacy compatibility](LEGACY_PIPELINE.md).
