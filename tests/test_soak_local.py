"""The opt-in real soak must clean up browser processes on timeout."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


spec = importlib.util.spec_from_file_location("soak_local", Path(__file__).parents[1] / "scripts/soak_local.py")
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


def test_soak_timeout_terminates_its_child_and_keeps_log(tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        soak.run_cycle([sys.executable, "-u", "-c", "import os,time; print(os.getpid(),flush=True); time.sleep(30)"],
                       os.environ.copy(), tmp_path, .5)
    pid = int((tmp_path / "browser.log").read_text().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_soak_retains_nonzero_exit_and_output(tmp_path):
    code = soak.run_cycle([sys.executable, "-c", "print('model failure'); raise SystemExit(2)"],
                          os.environ.copy(), tmp_path, 10)
    assert code == 2
    assert "model failure" in (tmp_path / "browser.log").read_text()
