import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str | None = None
    chunk_seconds: float = 300
    overlap_seconds: float = 2
    asr_retries: int = 1
    cpu_threads: int = 4
    model_dir: str = ".cache/models"
    local_files_only: bool = False
    process_timeout: float = 3600

    def __post_init__(self):
        for name in ("chunk_seconds", "overlap_seconds", "process_timeout"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if not 1 <= self.chunk_seconds <= 600:
            raise ValueError("chunk_seconds must be between 1 and 600")
        if not 0 <= self.overlap_seconds < self.chunk_seconds / 2:
            raise ValueError("overlap_seconds must be nonnegative and less than half a chunk")
        if not 0 <= self.asr_retries <= 5 or self.cpu_threads < 1:
            raise ValueError("asr_retries must be 0..5 and cpu_threads positive")
        if self.process_timeout <= 0:
            raise ValueError("process_timeout must be positive")

    @classmethod
    def from_env(cls):
        def get(name, default):
            return os.environ.get(f"VIDEOMIND_{name}", default)

        offline = get("LOCAL_FILES_ONLY", "false").lower()
        if offline not in ("true", "false"):
            raise ValueError("VIDEOMIND_LOCAL_FILES_ONLY must be true or false")
        return cls(
            model=get("MODEL", "base"), device=get("DEVICE", "cpu"),
            compute_type=get("COMPUTE_TYPE", "int8"), language=get("LANGUAGE", "") or None,
            chunk_seconds=float(get("CHUNK_SECONDS", "300")),
            overlap_seconds=float(get("OVERLAP_SECONDS", "2")),
            asr_retries=int(get("ASR_RETRIES", "1")), cpu_threads=int(get("CPU_THREADS", "4")),
            model_dir=get("MODEL_DIR", ".cache/models"), local_files_only=offline == "true",
            process_timeout=float(get("PROCESS_TIMEOUT", "3600")),
        )
