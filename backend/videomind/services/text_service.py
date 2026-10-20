"""Conservative comparison keys: scientific notation must retain its meaning."""
import unicodedata

COMPARISON_VERSION = "scientific_nfc_case_sensitive_v2"


def normalized_token(text: str) -> str:
    # NFC preserves superscripts/subscripts; NFKC and casefold do not preserve
    # scientific distinctions such as 10³/103, mW/MW and Co/CO.
    # Ignore one trailing full stop/comma only on plain alphabetic prose words.
    # Numeric punctuation, factorials, ellipses, primes, quotes and function
    # brackets stay significant. Ambiguous formatting is flagged, not erased.
    token = unicodedata.normalize("NFC", text).strip()
    if len(token) >= 4 and token[-1] in ".,。、" and token[:-1].isalpha():
        return token[:-1]
    return token
