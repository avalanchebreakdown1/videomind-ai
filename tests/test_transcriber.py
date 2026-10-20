from collections import namedtuple
from types import SimpleNamespace

from videomind.config import Settings
from videomind.models import Chunk
from videomind.services.transcription_service import FasterWhisperTranscriber


def test_adapter_consumes_lazy_segments_and_offsets_timestamps(tmp_path):
    W = namedtuple("W", "start end word probability")
    S = namedtuple("S", "start end text words")
    calls = []

    class Model:
        def transcribe(self, path, **kwargs):
            calls.append(kwargs)
            return iter([S(0, 1, " hello", [W(0.2, 0.8, " hello", 0.9)])]), SimpleNamespace(
                language="en", language_probability=0.95)

    adapter = FasterWhisperTranscriber(Settings())
    adapter._model = Model()
    result = adapter.transcribe(tmp_path / "chunk.wav", Chunk(1, 300, 600, 298, 602))
    assert result.words[0].start == 298.2
    assert result.segments[0]["words"][0]["start"] == 0.2
    assert calls[0]["word_timestamps"] is True
    assert calls[0]["vad_filter"] is True
