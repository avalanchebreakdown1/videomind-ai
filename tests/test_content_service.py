from copy import deepcopy
import re

import pytest

from videomind.services.content_service import prepare_document_source


def reviewed(text):
    tokens = re.findall(r"\s*\S+", text)
    return {"text": text.strip(), "audio_verification_performed": True,
            "words": [{"text": token, "start": i, "end": i + .5, "probability": .99,
                       "verification_status": "supported_by_second_asr"} for i, token in enumerate(tokens)],
            "uncertain_audio_spans": [], "warnings": []}


def test_greetings_and_chatter_removed_with_audit_and_original_preserved():
    source = reviewed("Hello friends, how are you? Welcome to my channel. Acceleration is the rate of change of velocity. "
                      "Please like and subscribe. Thanks for watching.")
    before = deepcopy(source)
    result = prepare_document_source(source)
    assert result["text"] == "Acceleration is the rate of change of velocity."
    assert result["counts"]["excluded_segments"] == 4
    assert {item["reason"] for item in result["excluded_segments"]} == {"greeting", "channel_welcome", "channel_promotion", "closing_chatter"}
    for item in result["excluded_segments"]:
        assert item["text"] == source["text"][item["source_char_start"]:item["source_char_end"]]
        assert item["source_word_indices"] and item["start"] is not None
    assert source == before
    assert not result["is_final_document"] and not result["fact_checked"]


def test_mixed_greeting_prefix_keeps_technical_intro_and_equation():
    source = reviewed("Hello friends, today we define force as F = m × a.")
    result = prepare_document_source(source)
    assert result["text"] == "today we define force as F = m × a."
    assert result["excluded_segments"][0]["reason"] == "greeting_prefix"
    assert source["text"].startswith("Hello friends")


@pytest.mark.parametrize("text", [
    'The program prints "Hello friends." as its output.',
    '"Hello friends." is a string literal.',
    "The output is shown next. Hello friends.",
    "Hello friends. This phrase is the output of the program.",
    "Hello World is a standard introductory program.",
    "Subscribe to the event stream to receive sensor readings.",
    "How are you calculating acceleration from these samples?",
    "Remember to preserve the negative sign in -5 m/s².",
    "This formula applies only when temperature remains constant.",
    "At 1.5 V, the current is 10 mA. This assumes a constant 150 Ω resistance.",
    "Hello friends, is the phrase being analyzed in this dataset.",
])
def test_technical_examples_qualifications_and_ambiguous_material_preserved(text):
    result = prepare_document_source(reviewed(text))
    assert result["text"] == text and result["excluded_segments"] == []


def test_uncertain_greeting_is_retained_and_marked_not_discarded():
    source = reviewed("Hello friends. A photon carries energy E = hν.")
    source["words"][0]["verification_status"] = "uncertain"
    source["uncertain_audio_spans"] = [{"start": 0, "end": .5}]
    result = prepare_document_source(source)
    assert result["text"] == source["text"]
    assert "[uncertain: Hello]" in result["annotated_text"]
    assert result["uncertain_audio_spans"] == source["uncertain_audio_spans"]
    assert result["excluded_segments"] == []


def test_uncertain_technical_word_keeps_status_in_document_source():
    source = reviewed("Hello friends. Energy is conserved.")
    source["words"][2]["verification_status"] = "uncertain"
    result = prepare_document_source(source)
    assert result["text"] == "Energy is conserved."
    assert "[uncertain: Energy]" in result["annotated_text"]
    assert result["source_words"][0]["source_word_index"] == 2
    assert result["source_words"][0]["verification_status"] == "uncertain"


def test_no_technical_material_is_not_filled_with_invented_facts():
    result = prepare_document_source(reviewed("Hello friends. Thanks for watching."))
    assert result["text"] == "" and not result["retained_segments"]
    assert result["counts"]["excluded_segments"] == 2


def test_returned_data_is_independent_of_input_and_global_policy():
    source = reviewed("Entropy measures uncertainty.")
    first = prepare_document_source(source)
    first["editorial_policy"]["preserve"].clear()
    first["source_words"][0]["text"] = "changed"
    second = prepare_document_source(source)
    assert "assumptions" in second["editorial_policy"]["preserve"]
    assert source["words"][0]["text"] == "Entropy"


def test_mismatched_text_is_rejected():
    source = reviewed("Energy is conserved.")
    source["text"] = "Different text"
    with pytest.raises(ValueError, match="does not match"):
        prepare_document_source(source)
