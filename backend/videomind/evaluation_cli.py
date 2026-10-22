"""Evaluate a local content suite. Exit 2 means failed or incomplete gates."""
import argparse
import json
from pathlib import Path
import sys

from .services.evaluation_suite_service import evaluate_suite, input_paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = args.suite.read_bytes()
        inputs = input_paths(manifest, args.suite.resolve().parent) | {args.suite.resolve()}
        if args.output.resolve() in inputs:
            raise ValueError("Report must be separate from every input")
        report = evaluate_suite(manifest, args.suite.resolve().parent)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(args.output)
        print(f"Content gate: {report['content_gate']}; production readiness: not assessed", file=sys.stderr)
        return 0 if report["content_gate"] == "passed" else 2
    except (OSError, ValueError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
