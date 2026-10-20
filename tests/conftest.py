from pathlib import Path
import struct
import wave

import pytest


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    target = tmp_path / "sample with spaces.wav"
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        # Distinct per-second levels expose wrong seek offsets as well as lengths.
        for second in range(7):
            handle.writeframes(struct.pack("<hh", second * 1000, second * 1000) * 8000)
    return target
