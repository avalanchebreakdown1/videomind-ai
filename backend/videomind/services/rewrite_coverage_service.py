"""Bounded, deterministic omission/invention checks, never factual verification."""
from decimal import Decimal
import re


NUMERIC_LITERAL = r"[+−-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?"
NUMBER = re.compile(r"(?<![\w.])" + NUMERIC_LITERAL + r"(?:\s*(?:k\b|million\b|billion\b))?", re.I)
UNITS = r"(?:mW|MW|W|cm²|m²|mm|cm|km|nm|µm|μm|mg|kg|Hz|kHz|MHz|GHz|Pa|kPa|°C|%|(?i:percent))"
QUANTITY = re.compile(r"(?<![\w.])(?P<number>" + NUMERIC_LITERAL + r")\s*(?P<unit>" + UNITS + r")(?!\w)")
NUMBER_WORDS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()


def numeric_values(text):
    values = {}
    for match in NUMBER.finditer(text):
        literal = match.group()
        parts = re.fullmatch(r"(" + NUMERIC_LITERAL + r")\s*(k|million|billion)?", literal, re.I)
        scale = {None: 1, "k": 1000, "million": 1_000_000, "billion": 1_000_000_000}[parts[2].lower() if parts[2] else None]
        key = str((Decimal(parts[1].replace(",", "").replace("−", "-")) * scale).normalize())
        values.setdefault(key, literal)
    return values


def quantitative_spans(source):
    """Bound evidence selection even when ASR produces a passage without stops."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", source):
        for match in NUMBER.finditer(sentence):
            # Distant technical examples must not make biography/chatter mandatory.
            nearby = sentence[max(0, match.start() - 80):match.end() + 80]
            if re.search(r"\b(?:subscribe|courses?|discount|coupon|revenue|million every year)\b|\d\s*%\s*off\b", nearby, re.I):
                continue
            meaningful_range = any(Decimal(a) != Decimal(b) for a, b in
                                   re.findall(r"(\d+)\s*(?:to|[–−-])\s*(\d+)", nearby, re.I))
            technical_range = meaningful_range and re.search(
                r"\b(?:range|values?|coverage|accuracy|precision|samples?|iterations?|threads?|days?|hours?|seconds?)\b", nearby, re.I)
            quantitative = re.search(r"\b(?:score|measured|measurement|compared|comparison)\b", nearby, re.I)
            literal = match.group()
            following = sentence[match.end():match.end() + 20]
            is_quantity = QUANTITY.match(sentence, match.start()) is not None
            if technical_range or quantitative or is_quantity or "." in literal or re.search(r"[eE][+−-]?\d", literal) or re.match(r"\s*(?:%|percent\b)", following, re.I):
                yield sentence, match


def required_numeric_values(source):
    """Keep explicit quantitative examples, excluding narrow advertising statements.

    This cannot identify every technical fact or resolve a garbled ASR value.
    Revenue/biographical claims are not forced into educational notes.
    """
    result = {}
    for sentence, match in quantitative_spans(source):
        result.update(numeric_values(match.group()))
    return result


def normalize_correction_quotes(result, source):
    """Restore a unique quote's exact source case/spacing, with an audit."""
    normalized = result.model_copy(deep=True)
    edits = []
    for correction in normalized.corrections:
        if correction.original in source:
            continue
        matches = list(re.finditer(re.escape(correction.original), source, re.I))
        reason = "unique_case_only_source_quote_match"
        if not matches and correction.original.split():
            pattern = r"\s+".join(re.escape(word) for word in correction.original.split())
            matches = list(re.finditer(pattern, source, re.I))
            reason = "unique_case_and_whitespace_source_quote_match"
        if len(matches) == 1:
            literal = matches[0].group()
            edits.append({"model_original": correction.original, "source_original": literal,
                          "reason": reason})
            correction.original = literal
    return normalized, edits


def coverage_findings(result, source, context=""):
    prose = "\n".join(s.heading + "\n" + s.explanation for s in result.sections)
    rendered = prose + "\n" + "\n".join(code for s in result.sections for code in s.code_examples)
    expected = required_numeric_values(source)
    actual = numeric_values(rendered)
    actual.update({str(Decimal(i).normalize()): word for i, word in enumerate(NUMBER_WORDS)
                   if re.search(r"\b" + word + r"\b", rendered, re.I)})
    allowed = numeric_values(source + " " + context)
    # Spoken small integers often become digits in explanations, not just code.
    allowed.update({str(Decimal(i).normalize()): word for i, word in enumerate(NUMBER_WORDS)
                    if re.search(r"\b" + word + r"\b", source + " " + context, re.I)})
    findings = []
    technical = set(re.findall(r"\b(?:functions?|variables?|algorithms?|equations?|datasets?|databases?|"
                               r"API|integers?|strings?|measurements?|operators?|traffic|backlinks|"
                               r"replication|typing|loops?|classes|objects?|compiler|interpreter)\b", source, re.I))
    if not result.sections and len(technical) >= 2:
        findings.append("Technical source content was omitted entirely; explain its concepts and examples rather than returning zero sections.")
    missing = [literal for key, literal in expected.items() if key not in actual]
    if missing:
        findings.append("Retain these source numerical examples with their conditions and relationships: " + ", ".join(missing))
    novel = [literal for key, literal in numeric_values(prose).items() if key not in allowed]
    if novel:
        findings.append("Remove numerical claims absent from the supplied source/context: " + ", ".join(novel))
    def quantity_key(match):
        unit = "%" if match['unit'].casefold() == "percent" else match['unit']
        return str(Decimal(match['number'].replace(",", "").replace("−", "-")).normalize()), unit
    actual_quantities = {quantity_key(m) for m in QUANTITY.finditer(rendered)}
    for sentence, number in quantitative_spans(source):
        match = QUANTITY.match(sentence, number.start())
        if match and quantity_key(match) not in actual_quantities:
            findings.append("Retain the exact source quantity and unit case: " + match.group())
    allowed_quantities = {quantity_key(m) for m in QUANTITY.finditer(source + " " + context)}
    for match in QUANTITY.finditer(prose):
        if quantity_key(match) not in allowed_quantities:
            findings.append("Remove a quantity/unit claim absent from the supplied source/context: " + match.group())
    audited_text = prose + "\n" + "\n".join(c.replacement for c in result.corrections)
    for url in re.findall(r"https?://[^\s<>\"')]+", audited_text):
        if url not in source + context:
            findings.append("Remove an invented URL: " + url)
    for correction in result.corrections:
        if correction.original not in source + context:
            findings.append("Correction original must be an exact excerpt from supplied source/context: " + correction.original)
        elif correction.original == correction.replacement:
            findings.append("Do not report an unchanged term as a correction: " + correction.original)
    return list(dict.fromkeys(findings))


def code_is_prose(text):
    """Catch the observed plain-English 'code' failure; accept other languages."""
    return bool(re.search(r"^(?:The |This |These |In the |[A-Z][\w ]{1,60} (?:is|are|means) )", text)
                and not re.search(r"[={}();]|^\s*(?:#|//|--)", text, re.M))
