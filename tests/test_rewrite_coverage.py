"""Controlled content regressions from actual short/long writing failures."""
from types import SimpleNamespace

import pytest

from videomind.config import Settings
from videomind.services.rewrite_coverage_service import coverage_findings, required_numeric_values, numeric_values, code_is_prose, normalize_correction_quotes
from videomind.services.direct_rewrite_service import DirectRewrite


def result(text, *, code=(), corrections=()):
    return SimpleNamespace(sections=[SimpleNamespace(heading="Experiment", explanation=text, code_examples=code)],
                           corrections=corrections)


def test_demo_comparison_must_retain_both_values_and_scope_values():
    source = "The organic traffic is 18.6 K compared with 18.4 K. The authority score is 26. Other metrics differ by 10 percent. Coverage is 10 to 15 percent."
    problems = coverage_findings(result("The displayed traffic is similar."), source)
    assert all(value in problems[0] for value in ("18.6 K", "18.4 K", "26", "10", "15"))
    assert not coverage_findings(result("The reported comparison gives traffic of 18,600 versus 18,400 and an authority score of 26. Other metrics differ by ±10%; coverage is only 10–15%."), source)


def test_no_invented_year_or_measurement_even_if_other_content_is_correct():
    assert "2024" in " ".join(coverage_findings(result("The product was created in 2024."), "The product was created recently."))
    assert "30" in " ".join(coverage_findings(result("The detector returns 30 mW."), "The detector returns .5 mW."))
    assert coverage_findings(result("The measured value is .5 mW."), "The measured value is −.5 mW.")
    assert not coverage_findings(result("The measured value is -0.5 mW."), "The measured value is −.5 mW.")
    assert not coverage_findings(result("The compared counts are 1,000,000 and 2,000,000."), "The compared counts are 1 Million and 2 MILLION.")


@pytest.mark.parametrize("changed", [".5 MW", "0.5 W", "5 mW"])
def test_unit_case_and_leading_decimal_are_not_interchangeable(changed):
    assert coverage_findings(result(changed), "The output is .5 mW.")
    assert not coverage_findings(result("The output is 0.5 mW."), "The output is .5 mW.")


def test_spoken_small_numbers_and_actual_source_context_are_allowed():
    assert not coverage_findings(result("Paid traffic measured zero."), "Paid traffic measured 0.")
    assert not coverage_findings(result("Use 2 variables."), "Create two variables.")
    assert not coverage_findings(result("The next comparison gives 42."), "Continue the comparison.", "The next value is 42.")


def test_advertising_quantities_not_required_but_technical_example_kept():
    values = list(required_numeric_values("Traffic is 18.6 K. Subscribe to get 20% off. There are 14 courses.").values())
    assert values == ["18.6 K"]
    assert required_numeric_values("Measured trade-off: 10 to 15 percent.")
    assert not required_numeric_values("There is no paid marketing, so 0-0 is there.")
    assert required_numeric_values("Measured traffic is 0-0.")
    assert required_numeric_values("The value ranges from 2 to 4.")
    assert not required_numeric_values("The comedy show ran from 1960 9 to 1974, around 10 years.")


def test_unpunctuated_asr_does_not_force_distant_comedy_dates_into_notes():
    source = ("The measured output is .5 mW " + "discussion of the language name " * 15
              + "the comedy show ran from 1960 9 to 1974 almost around 10 years")
    assert list(required_numeric_values(source).values()) == [".5"]
    assert not coverage_findings(result("The measured output is .5 mW."), source)


def test_scientific_notation_is_compared_as_a_whole_number_and_keeps_unit_case():
    source = "The measured output is −5e-4 W and the area is 2e2 cm²."
    assert set(numeric_values(source)) == {"-0.0005", "2E+2"}
    assert not coverage_findings(result("The measured output is -0.0005 W over 200 cm²."), source)
    assert coverage_findings(result("The measured output is -5 W over 2 cm²."), source)
    assert coverage_findings(result("The measured output is -0.0005 W over 200 m²."), source)


def test_extra_quantity_is_rejected_even_when_scalar_and_original_quantity_survive():
    problems = coverage_findings(result("The measured output is .5 mW, also .5 MW."), "The measured output is .5 mW.")
    assert "quantity/unit claim" in " ".join(problems)
    assert ".5 MW" in " ".join(problems)


def test_promotional_quantity_does_not_block_a_chatter_only_chunk():
    empty = SimpleNamespace(sections=[], corrections=[])
    assert not coverage_findings(empty, "Subscribe for a coupon for a 5 W promotional lamp.")


def test_percentage_is_not_satisfied_by_an_unrelated_count():
    source = "Other metrics differ by 10 percent."
    assert coverage_findings(result("The comparison uses 10 examples."), source)
    assert not coverage_findings(result("The reported metrics differ by ±10%."), source)


def test_unique_case_and_spacing_quote_restores_exact_source_with_audit():
    original = "Python is\nfunctional programming  "
    raw = DirectRewrite.model_validate({"sections": [], "corrections": [
        {"original": original, "replacement": "Python supports functional programming",
         "reason": "Clarify the programming paradigm."}]})
    source = "Here python is functional   programming and supports objects."
    fixed, edits = normalize_correction_quotes(raw, source)
    assert fixed.corrections[0].original == "python is functional   programming"
    assert raw.corrections[0].original == original
    assert edits[0]["reason"] == "unique_case_and_whitespace_source_quote_match"
    ambiguous = source + " Also python is functional programming."
    fixed, edits = normalize_correction_quotes(raw, ambiguous)
    assert not edits and fixed == raw


def test_unique_case_only_quote_normalization_preserves_model_and_source():
    raw = DirectRewrite.model_validate({"sections": [], "corrections": [
        {"original": "Reverse Engineer Anything", "replacement": "REA", "reason": "Term spelling"}]})
    fixed, edits = normalize_correction_quotes(raw, "Use reverse engineer anything here.")
    assert fixed.corrections[0].original == "reverse engineer anything"
    assert raw.corrections[0].original == "Reverse Engineer Anything"
    assert edits[0]["reason"] == "unique_case_only_source_quote_match"
    for source in ("Unrelated source.", "reverse engineer anything and reverse engineer anything"):
        fixed, edits = normalize_correction_quotes(raw, source)
        assert not edits and fixed == raw
        assert coverage_findings(fixed, source)


def test_corrections_require_real_exact_source_quotes():
    correction = SimpleNamespace(original="invented garbling", replacement="term")
    assert "exact excerpt" in " ".join(coverage_findings(result("Explanation.", corrections=[correction]), "Actual source."))
    correction.original, correction.replacement = "Actual", "Actual"
    assert "unchanged" in " ".join(coverage_findings(result("Explanation.", corrections=[correction]), "Actual source."))


def test_invented_links_and_technical_chunk_dropped_entirely():
    correction = SimpleNamespace(original="repository", replacement="https://example.org/invented")
    assert "invented URL" in " ".join(coverage_findings(result("Explanation.", corrections=[correction]), "The repository is public."))
    assert "invented URL" in " ".join(coverage_findings(result("See https://example.org/invented."), "No link was provided."))
    empty = SimpleNamespace(sections=[], corrections=[])
    assert "omitted entirely" in " ".join(coverage_findings(empty, "Variables contain objects; functions return values."))
    assert not coverage_findings(empty, "Thanks for watching.")


def test_prose_is_not_code_but_real_code_and_comments_are_kept():
    assert code_is_prose("The platform is a tool for reverse engineering")
    for code in ("print(value)", "const value = 42;", "# The platform is a tool", "git clone source", "The = 1"):
        assert not code_is_prose(code)


def test_default_primary_checkpoint_matches_local_app_and_never_downloads(monkeypatch):
    monkeypatch.delenv("VIDEOMIND_MODEL", raising=False)
    monkeypatch.delenv("VIDEOMIND_LOCAL_FILES_ONLY", raising=False)
    assert Settings().model == Settings.from_env().model == "small"
    assert Settings().local_files_only and Settings.from_env().local_files_only
