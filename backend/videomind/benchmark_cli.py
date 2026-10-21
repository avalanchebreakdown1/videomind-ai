"""Evaluate existing text artifacts without invoking ASR, Ollama or verification."""
import argparse
import json
from pathlib import Path
import sys

from .services.benchmark_service import evaluate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True, help="UTF-8 candidate transcript text")
    parser.add_argument("--notes", type=Path, required=True, help="UTF-8 candidate notes text")
    parser.add_argument("--review", type=Path, help="Optional hash-bound human notes review JSON")
    parser.add_argument("--output", type=Path, required=True, help="New report file; never overwritten")
    args = parser.parse_args(argv)
    try:
        inputs = [args.reference, args.transcript, args.notes]
        if args.review:
            inputs.append(args.review)
        if args.output.resolve() in {path.resolve() for path in inputs}:
            raise ValueError("Report must be separate from every input")
        report = evaluate(args.reference.read_bytes(), args.transcript.read_bytes(),
                          args.notes.read_bytes(), args.review.read_bytes() if args.review else None)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(args.output)
        print(f"WER: {report['transcription']['wer']:.4f}; notes: {report['notes']['status']}; "
              "accuracy acceptance: not assessed", file=sys.stderr)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
