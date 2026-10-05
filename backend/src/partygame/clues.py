"""Clue validation: one syllable, right language, no Forbidden Syllable."""

import re
import unicodedata
from functools import lru_cache
from typing import Literal

import pronouncing
from pythainlp.tokenize import syllable_tokenize

Language = Literal["th", "en"]

_THAI = re.compile(r"^[฀-๿]+$")
_LATIN = re.compile(r"^[a-z']+$")
_VOWEL_GROUPS = re.compile(r"[aeiouy]+")


class ClueRejected(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def normalize(text: str, lang: Language) -> str:
    text = unicodedata.normalize("NFC", text).strip()
    return text.lower() if lang == "en" else text


@lru_cache(maxsize=4096)
def _thai_syllables(text: str) -> tuple[str, ...]:
    return tuple(s for s in syllable_tokenize(text) if s.strip())


def _english_syllable_count(word: str) -> int:
    phones = pronouncing.phones_for_word(word)
    if phones:
        return min(pronouncing.syllable_count(p) for p in phones)
    # Fallback for words outside CMUdict: count vowel groups, ignoring a silent final "e".
    stem = word[:-1] if word.endswith("e") and len(word) > 2 else word
    return max(1, len(_VOWEL_GROUPS.findall(stem)))


def split_syllables(text: str, lang: Language) -> tuple[str, ...]:
    """Thai syllables, or words for English (English syllables can't be split reliably)."""
    words = normalize(text, lang).split()
    if lang == "th":
        return tuple(s for w in words for s in _thai_syllables(w))
    return tuple(words)


def syllable_count(text: str, lang: Language) -> int:
    words = normalize(text, lang).split()
    if lang == "th":
        return sum(len(_thai_syllables(w)) for w in words)
    return sum(_english_syllable_count(re.sub(r"[^a-z']", "", w) or w) for w in words)


def syllables_of(word: str, lang: Language) -> set[str]:
    """Pieces of a Secret Word that may not be used as a Clue."""
    word = normalize(word, lang)
    if lang == "th":
        pieces = {s for part in word.split() for s in _thai_syllables(part)}
    else:
        pieces = set(word.split())
    pieces.add(word.replace(" ", ""))
    return pieces


def _is_forbidden(clue: str, secret: str, lang: Language) -> bool:
    if clue in syllables_of(secret, lang):
        return True
    # English syllables can't be split reliably, so also refuse clues hidden inside the word.
    return lang == "en" and len(clue) >= 3 and clue in normalize(secret, lang).replace(" ", "")


def validate_clue(text: str, lang: Language, secret: str) -> str:
    """Return the normalized Clue, or raise ClueRejected."""
    clue = normalize(text, lang)
    if not clue:
        raise ClueRejected("empty")
    if any(ch.isspace() for ch in clue):
        raise ClueRejected("not_one_syllable")
    if lang == "th":
        if not _THAI.match(clue):
            raise ClueRejected("wrong_language")
        if len(_thai_syllables(clue)) != 1:
            raise ClueRejected("not_one_syllable")
    else:
        if not _LATIN.match(clue):
            raise ClueRejected("wrong_language")
        if _english_syllable_count(clue) != 1:
            raise ClueRejected("not_one_syllable")
    if _is_forbidden(clue, secret, lang):
        raise ClueRejected("forbidden_syllable")
    return clue


def first_syllable(transcript: str, lang: Language) -> str | None:
    """Cut a speech transcript down to its first syllable."""
    text = normalize(transcript, lang)
    if not text:
        return None
    first_word = text.split()[0]
    if lang == "th":
        pieces = _thai_syllables(first_word)
        return pieces[0] if pieces else None
    return re.sub(r"[^a-z']", "", first_word) or None
