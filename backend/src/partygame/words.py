"""Word Bank, Custom Words and Guess checking."""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from importlib import resources

from partygame.clues import Language

_INVISIBLE = re.compile(r"[\s​-‍﻿]+")
_REPEATED_MARK = re.compile(r"([ัิ-ฺ็-๎])\1+")
_THAI_ONLY = re.compile(r"^[฀-๿\s]+$")
_ENGLISH_ONLY = re.compile(r"^[A-Za-z' -]+$")


@dataclass(frozen=True)
class Word:
    text: str
    language: Language
    category: str = "custom"
    accepted: tuple[str, ...] = ()
    author_id: str | None = field(default=None, compare=False)

    @property
    def is_custom(self) -> bool:
        return self.author_id is not None


def normalize_guess(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = _INVISIBLE.sub("", text)
    return _REPEATED_MARK.sub(r"\1", text)


def is_correct_guess(guess: str, word: Word) -> bool:
    candidate = normalize_guess(guess)
    return bool(candidate) and candidate in {normalize_guess(w) for w in (word.text, *word.accepted)}


def detect_language(text: str) -> Language | None:
    text = text.strip()
    if not text:
        return None
    if _THAI_ONLY.match(text):
        return "th"
    if _ENGLISH_ONLY.match(text):
        return "en"
    return None


@cache
def word_bank(lang: Language) -> tuple[Word, ...]:
    raw = resources.files("partygame.data").joinpath(f"words_{lang}.json").read_text("utf-8")
    return tuple(
        Word(text=w["text"], language=lang, category=w["category"], accepted=tuple(w["accepted"]))
        for w in json.loads(raw)
    )
