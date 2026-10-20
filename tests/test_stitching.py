import pytest

from videomind.config import Settings
from videomind.models import Chunk, Transcript, Word
from videomind.services.chunking_service import plan_chunks
from videomind.services.stitching_service import LEGACY_VERSION, STITCHING_VERSION, render_text, stitch, stitch_with_report


@pytest.mark.parametrize("times", [[(9.6, 9.9), (10.1, 10.4)], [(10.1, 10.4), (9.6, 9.9)]])
def test_timestamp_drift_across_boundary_keeps_one_recognized_occurrence(times):
    chunks = [Chunk(0, 0, 10, 0, 12), Chunk(1, 10, 20, 8, 20)]
    results = [Transcript(chunk, [Word(start, end, " voltage", .99)], [], "en", 1)
               for chunk, (start, end) in zip(chunks, times)]
    assert render_text(stitch(results, chunks)) == "voltage"


def transcript(chunk, words):
    return Transcript(chunk, [Word(a, b, text, 0.9) for a, b, text in words], [], "en", 1)


def test_overlap_removed_by_time_without_removing_real_repetition():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    duplicated = [(9.8, 10.2, " yes"), (10.3, 10.7, " yes")]
    left = transcript(chunks[0], [(8, 8.5, "Say")] + duplicated)
    right = transcript(chunks[1], [(8, 8.5, " Say")] + duplicated + [(18, 19, " now.")])
    words = stitch([left, right], chunks)
    assert render_text(words) == "Say yes yes now."
    assert [word.start for word in words] == [8, 9.8, 10.3, 18]


@pytest.mark.parametrize("mode", ["missing", "reordered", "duplicate"])
def test_invalid_chunk_order(mode):
    chunks = plan_chunks(20, Settings(chunk_seconds=10))
    transcripts = [transcript(chunk, []) for chunk in chunks]
    if mode == "missing":
        transcripts.pop()
    elif mode == "reordered":
        transcripts.reverse()
    else:
        transcripts[1] = transcripts[0]
    with pytest.raises(ValueError):
        stitch(transcripts, chunks)


@pytest.mark.parametrize("words", [[(2, 1, "bad")], [(1, 2, " first"), (0, 1, " second")],
                                   [(0, 100, "bad")], [(float("nan"), 1, "bad")]])
def test_invalid_word_timestamps(words):
    chunks = plan_chunks(10, Settings())
    with pytest.raises(ValueError):
        stitch([transcript(chunks[0], words)], chunks)


def test_final_endpoint_and_unicode():
    chunks = plan_chunks(10, Settings())
    assert render_text(stitch([transcript(chunks[0], [(10, 10, "日本語。")])], chunks)) == "日本語。"


def test_real_repetitions_in_both_chunks_are_not_globally_deduplicated():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    repeated = [(9.0, 9.3, " very"), (9.5, 9.8, " very"), (10.0, 10.3, " important")]
    shifted = [(a + .25, b + .25, word) for a, b, word in repeated]
    assert render_text(stitch([transcript(chunks[0], repeated), transcript(chunks[1], shifted)], chunks)) == "very very important"


def test_different_repeated_occurrences_far_apart_remain_separate():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    assert render_text(stitch([transcript(chunks[0], [(8.1, 8.5, " yes")]),
                              transcript(chunks[1], [(11.0, 11.5, " yes")])], chunks)) == "yes yes"


def test_word_recognized_in_only_one_chunk_is_retained_with_review_evidence():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    left = [(8, 8.4, " force"), (10.5, 11, " acceleration")]
    right = [(8, 8.4, " force"), (9, 9.5, " mass"), (10.5, 11, " acceleration")]
    result = stitch_with_report([transcript(chunks[0], left), transcript(chunks[1], right)], chunks)
    assert render_text(result.words) == "force mass acceleration"
    assert result.boundaries[0]["requires_review"]
    assert any(item["reason"] == "recognized_in_one_chunk_only" for item in result.boundaries[0]["issues"])


def test_conflicting_scientific_units_are_alternatives_not_a_false_match():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    result = stitch_with_report([transcript(chunks[0], [(9.5, 10, " mW")]),
                                transcript(chunks[1], [(9.5, 10, " MW")])], chunks)
    boundary = result.boundaries[0]
    assert not boundary["matched_pairs"] and boundary["requires_review"]
    assert render_text(result.words) in {"mW", "MW"}
    assert boundary["left_candidates"][0]["text"] == " mW"
    assert boundary["right_candidates"][0]["text"] == " MW"


def test_zero_overlap_never_deduplicates_genuine_adjacent_words():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=0))
    result = stitch_with_report([transcript(chunks[0], [(9.5, 9.9, " no")]),
                                transcript(chunks[1], [(10.1, 10.5, " no")])], chunks)
    assert render_text(result.words) == "no no"
    assert result.boundaries[0]["issues"][0]["reason"] == "no_shared_audio_context"
    assert result.boundaries[0]["start"] == 9 and result.boundaries[0]["end"] == 11


def test_unknown_version_fails_and_legacy_behavior_remains_explicit():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    results = [transcript(chunks[0], [(10.1, 10.4, " voltage")]),
               transcript(chunks[1], [(9.6, 9.9, " voltage")])]
    assert render_text(stitch(results, chunks, version=LEGACY_VERSION)) == ""
    assert render_text(stitch(results, chunks, version=STITCHING_VERSION)) == "voltage"
    with pytest.raises(ValueError, match="Unsupported stitching version"):
        stitch(results, chunks, version="unknown-future-version")


def test_original_word_objects_are_not_mutated():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    results = [transcript(chunks[0], [(9.6, 9.9, " voltage")]),
               transcript(chunks[1], [(10.1, 10.4, " voltage")])]
    originals = [list(item.words) for item in results]
    output = stitch_with_report(results, chunks)
    assert [item.words for item in results] == originals
    assert output.words[0] in originals[0]


def test_alignment_budget_prevents_unbounded_token_matrix():
    chunks = plan_chunks(20, Settings(chunk_seconds=10, overlap_seconds=2))
    repeated = [(9 + i * .0001, 9.5 + i * .0001, " word") for i in range(400)]
    with pytest.raises(ValueError, match="token budget"):
        stitch([transcript(chunk, repeated) for chunk in chunks], chunks)
