"""Conservative, auditable preparation of source material for technical writing."""
import re
import unicodedata
from copy import deepcopy


TECHNICAL_DOCUMENT_POLICY = {
    "audience": "technical education",
    "tone": "formal, precise, technical",
    "exclude": ["greetings", "social pleasantries", "channel promotions", "closing chatter"],
    "preserve": ["definitions", "mechanisms", "equations", "units", "assumptions", "limitations",
                 "technical examples", "attribution", "transcription uncertainty"],
    "writing_requirements": ["Organize concepts independently instead of paraphrasing sentence by sentence.",
                             "Use precise terminology and evidence-linked explanations.",
                             "Do not present unverified claims or uncertain speech as established facts.",
                             "Retain relevant qualifications, source attribution and worked examples."],
}

RULES = {
    "greeting": re.compile(r"(?:hello|hi|hey)(?: (?:friends|everyone|everybody|students|folks|class|guys|all))?"
                           r"(?: how are you(?: all| today| doing)?)?|good (?:morning|afternoon|evening)(?: everyone|friends|class)?"),
    "social_pleasantry": re.compile(r"how are you(?: all| today| doing)?|i hope you(?: are| re) (?:all )?(?:doing well|well|fine)"),
    "channel_promotion": re.compile(r"(?:please )?(?:like (?:this|the) video|subscribe(?: to (?:my|our|the|this) channel)?|"
                                    r"like and subscribe(?: to (?:my|our|the|this) channel)?|"
                                    r"don['’]t forget to (?:like and subscribe|subscribe(?: to (?:my|our|the|this) channel)?))"),
    "closing_chatter": re.compile(r"(?:thank you|thanks) for (?:watching|joining|listening)|"
                                  r"see you in the next (?:video|lesson|lecture)|that['’]s all for today"),
    "channel_welcome": re.compile(r"welcome(?: back)? to (?:my|our|the|this) channel"),
}
EXAMPLE_CONTEXT = re.compile(r"\b(?:print|prints|printed|output|outputs|string|strings|literal|literals|"
                             r"phrase|phrases|greeting|greetings|example|examples|message|messages|quote|quoted)\b", re.I)
GREETING_PREFIX = re.compile(r"^(?:hello|hi|hey)\s+(?:friends|everyone|everybody|students|folks|class|guys|all)\s*[,!]\s*", re.I)
INTRO_AFTER_PREFIX = re.compile(r"^(?:today\b|in this\b|we (?:will|are going to|define|discuss|study)\b|let(?:'s| us)\b)", re.I)


def classify_chatter(text: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[,.!?;:…。！？、]", " ", normalized)
    normalized = " ".join(normalized.split())
    return next((reason for reason, pattern in RULES.items() if pattern.fullmatch(normalized)), None)


def prepare_document_source(reviewed: dict) -> dict:
    """Return a new source copy. Never mutate a transcript or promote claims to facts."""
    words = reviewed["words"]
    joined = "".join(word["text"] for word in words)
    text = joined.strip()
    if text != reviewed["text"]:
        raise ValueError("Reviewed text does not match its source words")
    leading = len(joined) - len(joined.lstrip())
    offsets, cursor = [], -leading
    for index, word in enumerate(words):
        end = cursor + len(word["text"])
        offsets.append((max(0, cursor), min(len(text), end), index))
        cursor = end

    ranges, start = [], 0
    for boundary in re.finditer(r"(?<=[.!?。！？])\s+|\n+", text):
        ranges.append((start, boundary.start()))
        start = boundary.end()
    ranges.append((start, len(text)))
    retained, excluded, previous = [], [], ""

    def segment(a, b, reason):
        indices = [i for left, right, i in offsets if left < b and right > a]
        touched = [words[i] for i in indices]
        return {"text": text[a:b], "reason": reason, "source_char_start": a, "source_char_end": b,
                "source_word_indices": indices,
                "start": min((word["start"] for word in touched), default=None),
                "end": max((word["end"] for word in touched), default=None),
                "verification_statuses": sorted({word.get("verification_status", "not_checked") for word in touched})}

    for position, (a, b) in enumerate(ranges):
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a == b:
            continue
        sentence = text[a:b]
        following = text[slice(*ranges[position + 1])].strip() if position + 1 < len(ranges) else ""
        explained_after = re.match(r"^(?:this (?:greeting|phrase|string|message|output)\b|(?:it|that) (?:is|was) (?:an? )?(?:example|greeting)\b)", following, re.I)
        protected = bool(EXAMPLE_CONTEXT.search(previous) or explained_after) or any(char in sentence for char in ('"', '“', '”', '`')) or sentence.startswith("'")
        reason = None if protected else classify_chatter(sentence)
        cut = b
        if reason is None and not protected:
            prefix = GREETING_PREFIX.match(sentence)
            if prefix and INTRO_AFTER_PREFIX.match(sentence[prefix.end():]):
                reason, cut = "greeting_prefix", a + prefix.end()
        if reason:
            candidate = segment(a, cut, reason)
            # A disputed greeting might actually be technical speech. Keep it for review.
            if "uncertain" in candidate["verification_statuses"]:
                retained.append(segment(a, b, "uncertain_transcription_preserved"))
            else:
                excluded.append(candidate)
                if cut < b:
                    retained.append(segment(cut, b, "technical_content_preserved"))
        else:
            retained.append(segment(a, b, "example_context_preserved" if protected else "content_preserved"))
        previous = sentence

    cleaned = " ".join(item["text"].strip() for item in retained)
    annotated_segments = []
    for item in retained:
        a, b = item["source_char_start"], item["source_char_end"]
        content = text[a:b]
        for left, right, i in reversed(offsets):
            if left < b and right > a and words[i].get("verification_status") == "uncertain":
                start, end = max(a, left) - a, min(b, right) - a
                fragment = content[start:end]
                prefix = fragment[:len(fragment) - len(fragment.lstrip())]
                content = content[:start] + prefix + "[uncertain: " + fragment.lstrip() + "]" + content[end:]
        annotated_segments.append(content.strip())
    # Word indices/statuses and original audio-review spans accompany the cleaned copy.
    kept_indices = sorted({i for item in retained for i in item["source_word_indices"]})
    return deepcopy({
        "kind": "technical_document_source", "is_final_document": False, "fact_checked": False,
        "text": cleaned, "annotated_text": " ".join(annotated_segments), "editorial_policy": TECHNICAL_DOCUMENT_POLICY,
        "retained_segments": retained, "excluded_segments": excluded,
        "source_words": [{"source_word_index": i, **words[i]} for i in kept_indices],
        "uncertain_audio_spans": reviewed.get("uncertain_audio_spans", []),
        "audio_verification_performed": reviewed.get("audio_verification_performed", False),
        "warnings": [*reviewed.get("warnings", []),
                     "Only clear standalone chatter and bounded greeting prefixes are excluded automatically.",
                     "Ambiguous or disputed material is retained for editorial review.",
                     "Educational source claims have not been independently fact-checked."],
        "counts": {"excluded_segments": len(excluded), "retained_segments": len(retained)},
    })
