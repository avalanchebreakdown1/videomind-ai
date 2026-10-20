"""Bounded, local-only semantic processing; never downloads models."""
from dataclasses import dataclass
import os
import math
from urllib.parse import urlsplit
import ipaddress


@dataclass(frozen=True)
class WritingSettings:
    endpoint: str = "http://127.0.0.1:11434"
    model: str = "llama3.1:8b"
    timeout_seconds: float = 180
    run_timeout_seconds: float = 3600
    chunk_chars: int = 3500
    direct_chunk_chars: int = 6000
    max_chunks: int = 80
    max_calls: int = 512
    max_concepts: int = 160
    num_ctx: int = 8192
    num_predict: int = 2200

    def __post_init__(self):
        url = urlsplit(self.endpoint)
        try:
            local = ipaddress.ip_address(url.hostname or "").is_loopback
            port = url.port
        except ValueError:
            local, port = False, None
        if not local or url.scheme != "http" or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
            raise ValueError("Ollama endpoint must be an HTTP loopback IP with no path or credentials")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Invalid Ollama port")
        if not self.model.strip() or len(self.model) > 200:
            raise ValueError("Specify an installed Ollama model")
        for name in ("timeout_seconds", "run_timeout_seconds"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 1 <= value <= 86400:
                raise ValueError(f"Invalid {name}")
        for name, low, high in (("chunk_chars", 500, 6000), ("direct_chunk_chars", 500, 6000), ("max_chunks", 1, 300), ("max_calls", 1, 1200),
                                ("max_concepts", 1, 500), ("num_ctx", 8192, 32768), ("num_predict", 512, 4096)):
            if not low <= getattr(self, name) <= high:
                raise ValueError(f"Invalid {name}")

    @classmethod
    def from_env(cls):
        defaults = cls()
        return cls(**{name: type(getattr(defaults, name))(os.environ.get("VIDEOMIND_WRITE_" + name.upper(), getattr(defaults, name)))
                      for name in defaults.__dataclass_fields__})
