import argparse
from dataclasses import replace
from pathlib import Path
import sys

from .config import Settings
from .ingestion_config import IngestionSettings
from .pipeline import run_pipeline
from .services.ingestion_service import run_youtube_pipeline


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "evaluate":
        from .evaluation_cli import main as evaluation_main
        return evaluation_main(argv[1:])
    if argv and argv[0] == "benchmark":
        from .benchmark_cli import main as benchmark_main
        return benchmark_main(argv[1:])
    if argv and argv[0] == "document":
        from .writing_cli import main as document_main
        return document_main(argv[1:])
    if argv and argv[0] == "verify":
        from .verification_cli import main as verify_main
        return verify_main(argv[1:])
    if argv and argv[0] == "restitch":
        from .restitch_cli import main as restitch_main
        return restitch_main(argv[1:])
    parser = argparse.ArgumentParser(description="Transcribe authorized local audio or a YouTube video (raw ASR; not verified).")
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--youtube-url", help="Single accessible YouTube video URL")
    parser.add_argument("--authorized", action="store_true", help="Confirm permission to process the YouTube video")
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for this run")
    parser.add_argument("--model", help="Faster-Whisper model name or local model directory")
    parser.add_argument("--language", help="Language code; auto-detect when omitted")
    parser.add_argument("--chunk-seconds", type=float)
    parser.add_argument("--overlap-seconds", type=float)
    parser.add_argument("--keep-chunks", action="store_true")
    args = parser.parse_args(argv)
    if (args.input is None) == (args.youtube_url is None):
        parser.error("Supply exactly one local input file or --youtube-url")
    try:
        settings = Settings.from_env()
        overrides = {name: getattr(args, name) for name in (
            "model", "language", "chunk_seconds", "overlap_seconds"
        ) if getattr(args, name) is not None}
        settings = replace(settings, **overrides)

        def progress(manifest):
            print(f"{manifest['progress']:3d}% {manifest['state']} "
                  f"({manifest['chunks_completed']}/{manifest.get('chunks_total', '?')} chunks)",
                  file=sys.stderr, flush=True)

        if args.youtube_url is not None:
            print("Retrieving authorized YouTube audio…", file=sys.stderr, flush=True)
            artifact = run_youtube_pipeline(args.youtube_url, args.output_dir, settings,
                IngestionSettings.from_env(), args.authorized, args.keep_chunks, progress)
        else:
            artifact = run_pipeline(args.input, args.output_dir, settings,
                                    keep_chunks=args.keep_chunks, on_progress=progress)
        print(artifact)
        return 0
    except KeyboardInterrupt:
        print("Interrupted; partial evidence retained in the run directory.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Transcription failed: {exc}", file=sys.stderr)
        return 1
