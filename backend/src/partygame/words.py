"""Word Bank, Custom Words and Guess checking."""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Literal

from partygame.clues import Language, split_syllables

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
    id: str | None = field(default=None, compare=False)

    @property
    def is_custom(self) -> bool:
        return self.author_id is not None


def normalize_guess(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = _INVISIBLE.sub("", text)
    return _REPEATED_MARK.sub(r"\1", text)


@dataclass(frozen=True)
class GuessResult:
    verdict: Literal["correct", "close", "wrong"]
    # For a close Guess: the syllables the Guesser already has right, in place.
    matched: tuple[str, ...] = ()


def judge_guess(guess: str, word: Word) -> GuessResult:
    """Correct (exact, or the answer said inside a sentence), close (a small typo, or some
    syllables right in place, e.g. "สนามมวย" for "สนามบิน"), or wrong."""
    candidate = normalize_guess(guess)
    if not candidate:
        return GuessResult("wrong")
    spellings = (word.text, *word.accepted)
    if any(normalize_guess(s) in candidate for s in spellings):
        return GuessResult("correct")
    guessed = split_syllables(guess, word.language)
    best: tuple[int, int, tuple[str, ...]] | None = None
    for spelling in spellings:
        answer = split_syllables(spelling, word.language)
        matched = tuple(a for a, g in zip(answer, guessed) if normalize_guess(a) == normalize_guess(g))
        distance = _edit_distance(normalize_guess(spelling), candidate)
        typo = distance <= _typo_allowance(normalize_guess(spelling))
        if (typo or matched) and (best is None or (len(matched), -distance) > best[:2]):
            best = (len(matched), -distance, matched)
    return GuessResult("close", best[2]) if best else GuessResult("wrong")


def is_correct_guess(guess: str, word: Word) -> bool:
    return judge_guess(guess, word).verdict == "correct"


def _typo_allowance(spelling: str) -> int:
    return 2 if len(spelling) >= 8 else 1 if len(spelling) >= 4 else 0


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


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
