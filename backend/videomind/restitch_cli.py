import argparse
from pathlib import Path
import sys

from .services.restitching_service import restitch_run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild stitching in a new run; preserve original transcripts and reuse ASR chunks.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(restitch_run(args.run_dir, args.output_dir))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Rebuilding failed: {exc}", file=sys.stderr)
        return 1
