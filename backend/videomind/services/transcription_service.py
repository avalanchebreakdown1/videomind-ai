from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..models import Chunk, Transcript, Word


class Transcriber(Protocol):
    def transcribe(self, path: Path, chunk: Chunk) -> Transcript: ...


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def transcribe(self, path: Path, chunk: Chunk) -> Transcript:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.settings.model, device=self.settings.device,
                compute_type=self.settings.compute_type, cpu_threads=self.settings.cpu_threads,
                download_root=self.settings.model_dir,
                local_files_only=self.settings.local_files_only,
            )
        segments, info = self._model.transcribe(
            str(path), language=self.settings.language, beam_size=5,
            word_timestamps=True, vad_filter=True, condition_on_previous_text=False,
        )
        # Iterate the lazy generator inside the retry boundary; only this chunk is decoded.
        raw, words = [], []
        for segment in segments:
            record = asdict(segment) if is_dataclass(segment) else segment._asdict()
            record["words"] = [asdict(word) if is_dataclass(word) else word._asdict()
                               for word in (segment.words or [])]
            raw.append(record)
            if segment.text.strip() and not segment.words:
                raise RuntimeError("ASR returned speech without word timestamps; cannot stitch safely")
            words.extend(Word(w.start + chunk.audio_start, w.end + chunk.audio_start,
                              w.word, w.probability) for w in (segment.words or []))
        return Transcript(chunk, words, raw, info.language, info.language_probability)
