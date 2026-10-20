import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from .config import Settings
from .services.verification_service import verify_run
from .verification_config import VerificationSettings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review selected audio sections without changing the raw transcript.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Completed transcription directory containing normalized.wav")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory outside the original run")
    parser.add_argument("--model", help="Different Faster-Whisper checkpoint; default small")
    parser.add_argument("--max-sections", type=int)
    args = parser.parse_args(argv)
    try:
        config = VerificationSettings.from_env()
        config = replace(config, **{name: getattr(args, name) for name in ("model", "max_sections") if getattr(args, name) is not None})
        result = verify_run(args.run_dir, args.output_dir, Settings.from_env(), config,
                            on_progress=lambda progress: print(f"{progress:3d}% verifying audio", file=sys.stderr, flush=True))
        report = json.loads(result.read_text())
        print(result)
        print(f"Audio coverage: {report['coverage_fraction']:.1%}; uncertain sections: {report['uncertain_sections']}; "
              f"failed sections: {report['failed_sections']}. Raw transcript unchanged.", file=sys.stderr)
        return 0 if not report["failed_sections"] else 2
    except KeyboardInterrupt:
        print("Verification interrupted; raw transcript preserved.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 1
