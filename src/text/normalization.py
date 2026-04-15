"""Normalization helpers for Turkish-friendly matching and retrieval."""

from __future__ import annotations

import re
import unicodedata

_TURKISH_ASCII_MAP = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "a",
    "acaba",
    "ama",
    "and",
    "bir",
    "bu",
    "can",
    "da",
    "de",
    "daha",
    "en",
    "for",
    "gore",
    "hangi",
    "i",
    "icin",
    "ile",
    "in",
    "is",
    "kimler",
    "ki",
    "me",
    "mi",
    "mu",
    "mu",
    "midir",
    "mu",
    "my",
    "ne",
    "nedir",
    "nasil",
    "of",
    "olan",
    "olarak",
    "or",
    "the",
    "to",
    "var",
    "ve",
    "veya",
    "what",
    "with",
    "ya",
    "zaman",
}

_TURKISH_HINTS = {
    "akademik",
    "bir",
    "bolum",
    "danisman",
    "ders",
    "gereksinim",
    "gpa",
    "kayit",
    "kural",
    "mezuniyet",
    "nedir",
    "not",
    "ogrenci",
    "politikasi",
    "sinav",
    "sinif",
    "yonerge",
}

_COMMON_SUFFIXES = (
    "lerinden",
    "larindan",
    "lerimiz",
    "larimiz",
    "leriniz",
    "lariniz",
    "lerine",
    "larina",
    "lerden",
    "lardan",
    "lerde",
    "larda",
    "lerin",
    "larin",
    "lerini",
    "larini",
    "sinden",
    "sindan",
    "sinde",
    "sinda",
    "sine",
    "sina",
    "siyle",
    "siyla",
    "leri",
    "lari",
    "lere",
    "lara",
    "nden",
    "ndan",
    "den",
    "dan",
    "ten",
    "tan",
    "nde",
    "nda",
    "de",
    "da",
    "te",
    "ta",
    "si",
    "sı",
    "su",
    "sü",
    "nin",
    "nin",
    "nun",
    "nun",
    "in",
    "un",
    "na",
    "ne",
    "ye",
    "ya",
    "yi",
    "yı",
    "yu",
    "yü",
    "i",
    "ı",
    "u",
    "ü",
)


def normalize_for_matching(text: str) -> str:
    """Fold Turkish characters and casing into an ASCII-ish search form."""

    mapped = text.translate(_TURKISH_ASCII_MAP)
    lowered = mapped.casefold()
    normalized = unicodedata.normalize("NFKD", lowered)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_marks).strip()


def tokenize_for_matching(text: str) -> tuple[str, ...]:
    normalized = normalize_for_matching(text)
    tokens = _TOKEN_RE.findall(normalized)
    reduced = tuple(_reduce_token(token) for token in tokens)
    return tuple(token for token in reduced if len(token) > 1 and token not in _STOPWORDS)


def augment_for_embedding(text: str) -> str:
    """Append an ASCII-folded variant so Turkish/non-Turkish spellings align better."""

    normalized = normalize_for_matching(text)
    if not normalized:
        return text

    original_normalized = re.sub(r"\s+", " ", text).strip().casefold()
    if normalized == original_normalized:
        return text
    return f"{text}\n\n{normalized}"


def looks_turkish(text: str) -> bool:
    if any(ch in text for ch in "çğıöşüÇĞİÖŞÜ"):
        return True

    tokens = set(tokenize_for_matching(text))
    if tokens & _TURKISH_HINTS:
        return True

    return any(
        token.startswith(hint) or hint.startswith(token)
        for token in tokens
        for hint in _TURKISH_HINTS
    )


def _reduce_token(token: str) -> str:
    reduced = token
    while True:
        next_value = _strip_one_suffix(reduced)
        if next_value == reduced:
            return reduced
        reduced = next_value


def _strip_one_suffix(token: str) -> str:
    for suffix in _COMMON_SUFFIXES:
        if len(token) - len(suffix) < 3:
            continue
        if token.endswith(suffix):
            return token[: -len(suffix)]
    return token
