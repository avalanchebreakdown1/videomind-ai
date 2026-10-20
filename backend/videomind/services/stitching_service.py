from dataclasses import asdict, dataclass
import math

from ..models import Chunk, Transcript, Word
from .text_service import normalized_token


LEGACY_VERSION = "midpoint_v1"
STITCHING_VERSION = "overlap_alignment_v2"
MAX_DRIFT_SECONDS = 1.0
MAX_ALIGNMENT_CELLS = 100_000


@dataclass(frozen=True)
class StitchResult:
    words: list[Word]
    boundaries: list[dict]


def validate(transcripts: list[Transcript], chunks: list[Chunk]):
    if not chunks or len(transcripts) != len(chunks):
        raise ValueError("Expected exactly one transcript per planned chunk")
    for i, (transcript, chunk) in enumerate(zip(transcripts, chunks)):
        if transcript.chunk != chunk or chunk.index != i:
            raise ValueError("Missing, reordered or mismatched transcript chunk")
        if i and abs(chunks[i - 1].core_end - chunk.core_start) > 1e-6:
            raise ValueError("Chunk cores must be contiguous")
        previous = -math.inf
        for word in transcript.words:
            if (not all(math.isfinite(v) for v in (word.start, word.end, word.probability))
                    or word.end < word.start or word.start < previous
                    or word.start < chunk.audio_start - 0.05
                    or word.end > chunk.audio_end + 0.25):
                raise ValueError("Invalid or unordered ASR word timestamps")
            previous = word.start


def midpoint(word: Word) -> float:
    return (word.start + word.end) / 2


def _matches(left: list[Word], right: list[Word]) -> list[tuple[int, int]]:
    """Monotonic one-to-one alignment: maximize anchors, then minimize drift."""
    n, m = len(left), len(right)
    if n * m > MAX_ALIGNMENT_CELLS:
        raise ValueError("Overlap alignment exceeds its token budget; use a shorter overlap. Original ASR chunks are preserved.")
    scores = [[(0, 0.0) for _ in range(m + 1)] for _ in range(n + 1)]
    steps = {}
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            options = [(scores[i + 1][j], "left"), (scores[i][j + 1], "right")]
            distance = abs(midpoint(left[i]) - midpoint(right[j]))
            token = normalized_token(left[i].text)
            if token and token == normalized_token(right[j].text) and distance <= MAX_DRIFT_SECONDS:
                score = scores[i + 1][j + 1]
                options.append(((score[0] + 1, score[1] - distance), "match"))
            best, action = max(options, key=lambda option: (option[0], option[1] == "match"))
            scores[i][j], steps[i, j] = best, action
    i, j, matches = 0, 0, []
    while i < n and j < m:
        action = steps[i, j]
        if action == "match":
            matches.append((i, j))
            i, j = i + 1, j + 1
        elif action == "left":
            i += 1
        else:
            j += 1
    return matches


def _unmatched(left: list[Word], right: list[Word], boundary: float, issues: list[dict]):
    if not left and not right:
        return []
    if not left or not right:
        selected = left or right
        issues.append({"reason": "recognized_in_one_chunk_only", "selected_words": [asdict(w) for w in selected]})
        return selected
    # Distinct nonoverlapping occurrences are retained, including genuine repeats
    # outside the alignment tolerance. Do not globally delete matching text.
    if left[-1].end <= right[0].start or right[-1].end <= left[0].start:
        issues.append({"reason": "unmatched_nonoverlapping_candidates",
                       "left_words": [asdict(w) for w in left], "right_words": [asdict(w) for w in right]})
        return sorted(left + right, key=lambda word: (word.start, word.end))
    # Conflicting hypotheses for the same time are alternatives, not consecutive
    # spoken words. Select one source sequence and retain both for audio review.
    centre = (min(left[0].start, right[0].start) + max(left[-1].end, right[-1].end)) / 2
    choose_left = centre < boundary
    issues.append({"reason": "conflicting_overlap_candidates", "selected_side": "left" if choose_left else "right",
                   "left_words": [asdict(w) for w in left], "right_words": [asdict(w) for w in right]})
    return left if choose_left else right


def stitch_with_report(transcripts: list[Transcript], chunks: list[Chunk]) -> StitchResult:
    validate(transcripts, chunks)
    output = list(transcripts[0].words)
    boundaries = []
    for i in range(1, len(chunks)):
        before, current = chunks[i - 1], chunks[i]
        boundary = current.core_start
        overlap_start, overlap_end = max(before.audio_start, current.audio_start), min(before.audio_end, current.audio_end)
        right_words = transcripts[i].words
        if overlap_end <= overlap_start:
            output.extend(right_words)
            boundaries.append({"boundary": boundary, "start": max(chunks[0].core_start, boundary - MAX_DRIFT_SECONDS),
                               "end": min(chunks[-1].core_end, boundary + MAX_DRIFT_SECONDS),
                               "requires_review": True, "issues": [{"reason": "no_shared_audio_context"}]})
            continue
        # Include near-edge words whose two timestamp estimates straddle the
        # shared-context edge; correspondence still requires <= 1 second drift.
        start, end = overlap_start - MAX_DRIFT_SECONDS, overlap_end + MAX_DRIFT_SECONDS
        prefix = [word for word in output if midpoint(word) < start]
        left = [word for word in output if midpoint(word) >= start]
        right = [word for word in right_words if midpoint(word) <= end]
        tail = [word for word in right_words if midpoint(word) > end]
        matches = _matches(left, right)
        issues, merged = [], []
        a, b = 0, 0
        for li, ri in matches:
            merged.extend(_unmatched(left[a:li], right[b:ri], boundary, issues))
            merged.append(left[li])
            a, b = li + 1, ri + 1
        merged.extend(_unmatched(left[a:], right[b:], boundary, issues))
        if matches and len(matches) < 2:
            issues.append({"reason": "single_word_alignment_is_ambiguous"})
        if any(abs(midpoint(left[li]) - midpoint(right[ri])) > .05 for li, ri in matches):
            issues.append({"reason": "timestamp_drift_reconciled"})
        ordered = sorted(merged, key=lambda word: (word.start, word.end))
        if ordered != merged:
            issues.append({"reason": "candidate_order_reconciled_by_audio_time"})
        output = prefix + ordered + tail
        boundaries.append({"boundary": boundary, "start": max(chunks[0].core_start, start),
                           "end": min(chunks[-1].core_end, end), "requires_review": bool(issues), "issues": issues,
                           "matched_pairs": [{"left": asdict(left[li]), "right": asdict(right[ri])} for li, ri in matches],
                           "left_candidates": [asdict(w) for w in left], "right_candidates": [asdict(w) for w in right]})
    words = [word for word in output if chunks[0].core_start <= midpoint(word) <= chunks[-1].core_end]
    return StitchResult(words, boundaries)


def _legacy_stitch(transcripts: list[Transcript], chunks: list[Chunk]) -> list[Word]:
    if not chunks or len(transcripts) != len(chunks):
        raise ValueError("Expected exactly one transcript per planned chunk")
    output = []
    for i, (transcript, chunk) in enumerate(zip(transcripts, chunks)):
        if transcript.chunk != chunk or chunk.index != i:
            raise ValueError("Missing, reordered or mismatched transcript chunk")
        if i and abs(chunks[i - 1].core_end - chunk.core_start) > 1e-6:
            raise ValueError("Chunk cores must be contiguous")
        previous = -math.inf
        for word in transcript.words:
            if (not all(math.isfinite(v) for v in (word.start, word.end, word.probability))
                    or word.end < word.start or word.start < previous
                    or word.start < chunk.audio_start - 0.05
                    or word.end > chunk.audio_end + 0.25):
                raise ValueError("Invalid or unordered ASR word timestamps")
            previous = word.start
            midpoint = (word.start + word.end) / 2
            if chunk.core_start <= midpoint < chunk.core_end or (
                i == len(chunks) - 1 and midpoint == chunk.core_end
            ):
                output.append(word)
    return output


def stitch(transcripts: list[Transcript], chunks: list[Chunk], *, version: str = STITCHING_VERSION) -> list[Word]:
    if version == LEGACY_VERSION:
        return _legacy_stitch(transcripts, chunks)
    if version != STITCHING_VERSION:
        raise ValueError(f"Unsupported stitching version: {version}")
    return stitch_with_report(transcripts, chunks).words


def render_text(words: list[Word]) -> str:
    # Whisper includes spacing in word tokens, including language-specific punctuation.
    return "".join(word.text for word in words).strip()
