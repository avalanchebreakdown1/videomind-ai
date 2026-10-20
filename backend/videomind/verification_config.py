from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class VerificationSettings:
    model: str = "small"
    word_threshold: float = 0.65
    section_seconds: float = 30
    context_seconds: float = 2
    recheck_context_seconds: float = 6
    gap_seconds: float = 8
    alignment_tolerance_seconds: float = 1
    max_sections: int = 200
    recheck: bool = True

    def __post_init__(self):
        for field in ("word_threshold", "section_seconds", "context_seconds", "recheck_context_seconds", "gap_seconds", "alignment_tolerance_seconds"):
            if not math.isfinite(getattr(self, field)):
                raise ValueError(f"{field} must be finite")
        if not 0 < self.word_threshold <= 1 or not 2 <= self.section_seconds <= 60:
            raise ValueError("Threshold must be in (0,1] and section_seconds in [2,60]")
        if not 0 <= self.context_seconds <= self.recheck_context_seconds <= 15:
            raise ValueError("Context must be 0 <= initial <= recheck <= 15 seconds")
        if self.gap_seconds <= 0 or not 1 <= self.max_sections <= 10000:
            raise ValueError("gap_seconds must be positive and max_sections in [1,10000]")
        if not 0 <= self.alignment_tolerance_seconds <= 5:
            raise ValueError("Alignment tolerance must be between 0 and 5 seconds")
        if not self.model.strip():
            raise ValueError("A separate verification model is required")

    @classmethod
    def from_env(cls):
        def get(name, default):
            return os.environ.get(f"VIDEOMIND_VERIFY_{name}", default)
        recheck = get("RECHECK", "true").lower()
        if recheck not in {"true", "false"}:
            raise ValueError("VIDEOMIND_VERIFY_RECHECK must be true or false")
        return cls(model=get("MODEL", "small"), word_threshold=float(get("WORD_THRESHOLD", "0.65")),
                   section_seconds=float(get("SECTION_SECONDS", "30")),
                   context_seconds=float(get("CONTEXT_SECONDS", "2")),
                   recheck_context_seconds=float(get("RECHECK_CONTEXT_SECONDS", "6")),
                   gap_seconds=float(get("GAP_SECONDS", "8")), max_sections=int(get("MAX_SECTIONS", "200")),
                   alignment_tolerance_seconds=float(get("ALIGNMENT_TOLERANCE_SECONDS", "1")),
                   recheck=recheck == "true")
