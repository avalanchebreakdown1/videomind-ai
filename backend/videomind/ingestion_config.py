from dataclasses import dataclass
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class IngestionSettings:
    storage_dir: Path = Path("storage")
    max_bytes: int = 256 * 1024 * 1024
    max_duration: float = 4 * 3600
    download_timeout: float = 900
    socket_timeout: float = 20
    max_jobs: int = 5

    def __post_init__(self):
        if self.max_bytes < 1 or self.max_jobs < 1:
            raise ValueError("Byte and job limits must be positive")
        for value in (self.max_duration, self.download_timeout, self.socket_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Duration and timeout limits must be finite and positive")

    @classmethod
    def from_env(cls):
        def get(name, default):
            return os.environ.get(f"VIDEOMIND_{name}", default)
        return cls(
            storage_dir=Path(get("STORAGE_DIR", "storage")),
            max_bytes=int(get("MAX_SOURCE_BYTES", str(256 * 1024 * 1024))),
            max_duration=float(get("MAX_DURATION_SECONDS", "14400")),
            download_timeout=float(get("DOWNLOAD_TIMEOUT", "900")),
            socket_timeout=float(get("SOCKET_TIMEOUT", "20")),
            max_jobs=int(get("MAX_JOBS", "5")),
        )
