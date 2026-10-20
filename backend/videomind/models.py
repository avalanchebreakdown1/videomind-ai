from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    core_start: float
    core_end: float
    audio_start: float
    audio_end: float


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str
    probability: float


@dataclass(frozen=True)
class Transcript:
    chunk: Chunk
    words: list[Word]
    segments: list[dict]
    language: str
    language_probability: float
