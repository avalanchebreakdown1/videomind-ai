"""Repeat real browser/audio workflows against already running local servers.

No fixtures or downloads. Each cycle retains its browser report and server jobs.
Run from the project root with the same cached models used for real E2E tests.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


PROJECT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def code_digest():
    files = [PROJECT / "scripts/soak_local.py"]
    for directory in ("backend/videomind", "frontend/app", "frontend/components", "frontend/lib", "frontend/e2e-real"):
        files.extend(p for p in (PROJECT / directory).rglob("*")
                     if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".css"})
    files.extend(PROJECT / p for p in ("frontend/playwright.real.config.ts", "frontend/package-lock.json"))
    result = hashlib.sha256()
    for path in sorted(set(files)):
        result.update(str(path.relative_to(PROJECT)).encode())
        result.update(digest(path).encode())
    return result.hexdigest()


def run_cycle(command, environment, output, timeout):
    with (output / "browser.log").open("xb") as log:
        process = subprocess.Popen(command, cwd=PROJECT / "frontend", env=environment,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--interval-seconds", type=int, default=600)
    args = parser.parse_args()
    if not 0 < args.hours <= 48 or not 60 <= args.interval_seconds <= 3600:
        parser.error("hours must be >0 and <=48; interval must be 60–3600 seconds")
    audio, output = args.audio.resolve(), args.output.resolve()
    if not audio.is_file():
        parser.error("audio must be an existing authorized local recording")
    node = PROJECT / "frontend/node_modules/node/bin/node"
    playwright = PROJECT / "frontend/node_modules/@playwright/test/cli.js"
    if not node.is_file() or not playwright.is_file():
        parser.error("install frontend dependencies before running the soak")
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment["VIDEOMIND_REAL_AUDIO_PATH"] = str(audio)
    environment.pop("VIDEOMIND_REAL_VIDEO_URL", None)
    source_hash, code_hash = digest(audio), code_digest()
    started = time.monotonic()
    deadline = started + args.hours * 3600
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "requested_hours": args.hours,
              "audio": str(audio), "audio_sha256": source_hash, "code_sha256": code_hash,
              "state": "running", "cycles": [], "content_accuracy_verified": False}

    def save():
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        temporary = output / "report.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(output / "report.json")

    save()
    try:
        while time.monotonic() < deadline:
            if digest(audio) != source_hash or code_digest() != code_hash:
                raise RuntimeError("Source or tested code changed during the soak; restart in a fresh directory")
            cycle_started = time.monotonic()
            # Leave enough time for a cycle like the preceding one.
            if report["cycles"] and deadline - cycle_started < report["cycles"][-1]["elapsed_seconds"] + 60:
                time.sleep(max(0, min(1, deadline - cycle_started)))
                continue
            cycle = output / f"cycle-{len(report['cycles']) + 1:04d}"
            cycle.mkdir()
            environment["PLAYWRIGHT_HTML_OUTPUT_DIR"] = str(cycle / "html")
            environment["PLAYWRIGHT_JSON_OUTPUT_FILE"] = str(cycle / "results.json")
            command = [str(node), str(playwright), "test", "--config=playwright.real.config.ts",
                       "--grep", "real long audio", "--reporter=line,json", "--output", str(cycle / "artifacts")]
            print(f"Starting {cycle.name}; elapsed {report['elapsed_seconds']} seconds", flush=True)
            try:
                code = run_cycle(command, environment, cycle, min(90 * 60 + 60, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                code = 124
            # A zero exit with skipped tests cannot satisfy the soak.
            stats = json.loads((cycle / "results.json").read_text())["stats"] if code == 0 else {}
            passed = code == 0 and stats["expected"] == 1 and stats["skipped"] == 0 and stats["unexpected"] == 0
            report["cycles"].append({"directory": cycle.name, "returncode": code, "passed": passed,
                                     "elapsed_seconds": round(time.monotonic() - cycle_started, 2),
                                     "free_disk_bytes": shutil.disk_usage(output).free})
            save()
            if not passed:
                raise RuntimeError(f"Real workflow failed in {cycle.name}; inspect its browser.log and artifacts")
            # Sleep in short interruptible intervals, leaving no child job running.
            next_cycle = min(deadline, cycle_started + args.interval_seconds)
            while time.monotonic() < next_cycle:
                time.sleep(max(0, min(1, next_cycle - time.monotonic())))
        if digest(audio) != source_hash or code_digest() != code_hash:
            raise RuntimeError("Source or tested code changed during the soak")
        report["state"] = "passed"
    except KeyboardInterrupt:
        report["state"] = "interrupted"
    except Exception as error:
        report.update(state="failed", error=str(error))
    finally:
        save()
    print(f"{report['state']}: {output / 'report.json'}", flush=True)
    return 0 if report["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
