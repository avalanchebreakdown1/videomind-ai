import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from .writing_config import WritingSettings
from .services.writing_pipeline import generate_document


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rewrite a transcript into technical educational notes using local Ollama.")
    parser.add_argument("--pipeline", choices=("direct", "legacy"), default="direct", help="Direct rewrite (default), or the previous extraction/review pipeline")
    parser.add_argument("--source-dir", required=True, type=Path, help="Completed transcription or verification directory")
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory outside the source")
    parser.add_argument("--model", help="Installed Ollama model (default llama3.1:8b)")
    parser.add_argument("--source-title")
    parser.add_argument("--source-url", help="Attribution only; this URL is never fetched")
    parser.add_argument("--source-creator")
    parser.add_argument("--reuse-knowledge", type=Path, help="Prior writing run with completed extraction; validated against source and saved responses")
    parser.add_argument("--reuse-model-calls", type=Path, help="Prior run whose exact matching model calls can be replayed with provenance")
    args = parser.parse_args(argv)
    try:
        settings = WritingSettings.from_env()
        if args.model:
            settings = replace(settings, model=args.model)
        result = generate_document(args.source_dir, args.output_dir, settings, pipeline=args.pipeline,
            title=args.source_title, url=args.source_url, creator=args.source_creator,
            reuse_knowledge=args.reuse_knowledge,
            reuse_model_calls=args.reuse_model_calls,
            on_progress=lambda stage, percent: print(f"{percent:3d}% {stage}", file=sys.stderr, flush=True))
        report = json.loads(result.with_name("quality.json").read_text())
        print(result)
        print(f"Status: {report['state']}; {len(report['issues'])} audit findings. External facts have not been independently checked.", file=sys.stderr)
        return 2 if report["state"] == "needs_review" else 0
    except KeyboardInterrupt:
        print("Interrupted; source unchanged and partial document evidence retained.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Document generation failed: {exc}", file=sys.stderr)
        return 1
