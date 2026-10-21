from videomind.services.direct_rewrite_service import DirectRewrite
from videomind.services.rewrite_integrity_service import required_constructs, rewrite_problems, repair_known_regressions


def candidate(text):
    return DirectRewrite.model_validate({"sections": [{"heading": "Types", "explanation": text, "code_examples": []}], "corrections": []})


def test_pass_is_required_only_when_taught_as_a_python_construct():
    assert required_constructs("Python has a keyword called pass for an empty block.", "Lesson") == ["pass"]
    assert required_constructs("The signal can pass through glass.", "Physics") == []
    assert rewrite_problems(candidate("Functions reuse code."), ["pass"], True)
    assert not rewrite_problems(candidate("The pass statement is a no-op placeholder."), ["pass"], True)


def test_known_type_and_scope_errors_are_rejected_without_rejecting_qualified_explanations():
    for text in ("Variable names must be unique.", "When combining different data types, explicit type conversion is required.",
                 "Python supports dynamic type conversion."):
        assert rewrite_problems(candidate(text), [], True)
    assert not rewrite_problems(candidate("Names may be rebound. For int + str, convert explicitly; int + float needs no explicit conversion."), [], True)


def test_reference_repairs_are_audited_and_do_not_change_original_candidate():
    original = candidate("Variable names must be unique. When combining different data types, explicit type conversion is required.")
    repaired, edits = repair_known_regressions(original, ["pass"], True)
    assert not rewrite_problems(repaired, ["pass"], True)
    assert "must be unique" in original.sections[0].explanation
    assert len(edits) == 3 and all(e["reference"].startswith("https://docs.python.org/") for e in edits)
    unchanged, edits = repair_known_regressions(original, [], False)
    assert unchanged == original and not edits


def test_presenter_narration_is_rejected_but_scoped_observations_and_code_are_kept():
    for text in ("The speaker discusses replication limits.", "The video explains reverse engineering.",
                 "Krish uses a local prototype.", "In this case, the author observed inconsistent results."):
        assert rewrite_problems(candidate(text), [], False, creator="Krish Naik")
    result = candidate("In the reported comparison, traffic estimates were 18.6 K and 18.4 K. "
                       "Python uses dynamic typing. The prototype does not establish backend equivalence.")
    result.sections[0].code_examples = ['print("The speaker discusses replication")']
    assert not rewrite_problems(result, [], False, creator="Krish Naik")
