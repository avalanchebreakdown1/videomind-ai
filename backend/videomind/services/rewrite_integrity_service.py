"""Narrow regressions from observed failures; not a general factual verifier."""
import re

ASSIGNMENT_REFERENCE = "https://docs.python.org/3.13/reference/executionmodel.html#binding-of-names"
NUMERIC_REFERENCE = "https://docs.python.org/3.13/library/stdtypes.html#numeric-types-int-float-complex"
PASS_REFERENCE = "https://docs.python.org/3.13/reference/simple_stmts.html#the-pass-statement"


def repair_known_regressions(result, required, python_lesson):
    """Selected reference-backed editorial edits, not a scientific fact-checker."""
    data, edits = result.model_dump(), []
    if not python_lesson:
        return result, edits
    rules = [
        (r"\b(?:variable )?names must be unique\b",
         "Names identify bindings within their scope and may be reassigned or reused in different scopes.", ASSIGNMENT_REFERENCE),
        (r"(?:when combining different data types|combining different types).{0,50}(?:conversion is required|require.{0,20}conversion)",
         "Explicit conversion is needed for incompatible operands such as an integer and a string; mixed numeric operands such as int and float can be combined directly.", NUMERIC_REFERENCE),
        (r"(?:automatically handle type conversion|supports dynamic type conversion)",
         "A name may be rebound to an object of a different type; rebinding does not convert the original object.", ASSIGNMENT_REFERENCE),
    ]
    for section in data["sections"]:
        sentences = re.split(r"(?<=[.!?])\s+", section["explanation"])
        for index, sentence in enumerate(sentences):
            for pattern, replacement, reference in rules:
                if re.search(pattern, sentence, re.I):
                    edits.append({"original": sentence, "replacement": replacement, "reference": reference,
                                  "method": "selected_reference_editorial_rule"})
                    sentences[index] = replacement
                    break
        section["explanation"] = " ".join(sentences)
    rendered = " ".join(s["heading"] + " " + s["explanation"] + " " + " ".join(s["code_examples"]) for s in data["sections"])
    if "pass" in required and not re.search(r"\bpass\b", rendered, re.I):
        explanation = "The pass statement performs no operation. It supplies a statement where Python syntax requires a block, such as an unfinished function body."
        edits.append({"original": None, "replacement": explanation, "reference": PASS_REFERENCE,
                      "method": "restore_explicitly_taught_keyword"})
        if len(data["sections"]) < 6:
            data["sections"].append({"heading": "Placeholder statements", "explanation": explanation, "code_examples": []})
        else:
            data["sections"][-1]["explanation"] += " " + explanation
    return type(result).model_validate(data), edits


def required_constructs(source, topic):
    if not re.search(r"\bpython\b", source + " " + topic, re.I):
        return []
    return ["pass"] if re.search(r"(?:keyword|word|statement).{0,80}\bpass\b", source, re.I) else []


def rewrite_problems(result, required, python_lesson):
    text = "\n".join(s.heading + "\n" + s.explanation + "\n" + "\n".join(s.code_examples) for s in result.sections)
    problems = [f"Explain the taught {word!r} keyword; it was omitted." for word in required
                if not re.search(r"\b" + re.escape(word) + r"\b", text, re.I)]
    if python_lesson:
        for section in result.sections:
            prose = section.explanation
            if re.search(r"\b(?:variable )?names must be unique\b", prose, re.I):
                problems.append("Names can be rebound and reused in different scopes; do not claim global uniqueness.")
            if re.search(r"(?:when combining different data types|combining different types).{0,50}(?:conversion is required|require.{0,20}conversion)", prose, re.I):
                problems.append("Scope explicit conversion to incompatible operands such as int + str; int + float works without explicit conversion.")
            if re.search(r"(?:automatically handle type conversion|supports dynamic type conversion)", prose, re.I):
                problems.append("Distinguish name rebinding from converting an object; do not promise arbitrary automatic conversion.")
    return list(dict.fromkeys(problems))
