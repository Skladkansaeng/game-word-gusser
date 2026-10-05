"""Game rules. Every mutating call takes `now` so the rules are testable without a real clock.

Vocabulary follows CONTEXT.md: Lobby > Match > Cycle > Round > Clue Chain.
"""

import random
import secrets
import string
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from partygame.clues import ClueRejected, first_syllable, validate_clue
from partygame.words import Word, detect_language, is_correct_guess, word_bank

MIN_PLAYERS = 3
MAX_PLAYERS = 12
MAX_CYCLES = 5
MAX_CUSTOM_WORDS_PER_PLAYER = 20
AWAY_GRACE_SECONDS = 5.0
GUESS_SECONDS = 20.0
REVEAL_SECONDS = 6.0

GUESSER_POINTS = 3
CLUE_GIVER_POINTS = 1
WRONG_GUESS_PENALTY = -1

COLORS = ["#e4572e", "#29335c", "#f3a712", "#669bbc", "#a8c686", "#8e44ad",
          "#16a085", "#d35400", "#2c3e50", "#c0392b", "#7f8c8d", "#f06292"]

PlayMode = Literal["online", "in_person"]
WordSource = Literal["bank", "mixed", "custom"]


class GameError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Settings:
    play_mode: PlayMode = "online"
    word_language: Literal["th", "en"] = "th"
    word_source: WordSource = "bank"
    cycles: int = 1
    round_seconds: int = 90
    clue_seconds: int = 10

    _CHOICES = {
        "play_mode": ("online", "in_person"),
        "word_language": ("th", "en"),
        "word_source": ("bank", "mixed", "custom"),
    }
    _RANGES = {"cycles": (1, MAX_CYCLES), "round_seconds": (30, 300), "clue_seconds": (5, 60)}
    # The client speaks camelCase, matching as_dict().
    _WIRE_NAMES = {"playMode": "play_mode", "wordLanguage": "word_language", "wordSource": "word_source",
                   "roundSeconds": "round_seconds", "clueSeconds": "clue_seconds"}

    def update(self, changes: dict[str, Any]) -> None:
        changes = {self._WIRE_NAMES.get(key, key): value for key, value in changes.items()}
        for key, value in changes.items():
            if key in self._CHOICES:
                if value not in self._CHOICES[key]:
                    raise GameError("invalid_setting")
            elif key in self._RANGES:
                lo, hi = self._RANGES[key]
                if not isinstance(value, int) or not lo <= value <= hi:
                    raise GameError("invalid_setting")
            else:
                raise GameError("invalid_setting")
        for key, value in changes.items():
            setattr(self, key, value)

    def as_dict(self) -> dict[str, Any]:
        return {
            "playMode": self.play_mode,
            "wordLanguage": self.word_language,
            "wordSource": self.word_source,
            "cycles": self.cycles,
            "roundSeconds": self.round_seconds,
            "clueSeconds": self.clue_seconds,
        }


@dataclass
class Player:
    id: str
    token: str
    name: str
    color: str
    joined_at: float
    connected: bool = True
    disconnected_at: float | None = None
    kicked: bool = False

    def is_away(self, now: float) -> bool:
        if self.kicked:
            return True
        return not self.connected and now - (self.disconnected_at or now) >= AWAY_GRACE_SECONDS


@dataclass
class Clue:
    player_id: str
    text: str


@dataclass
class Round:
    number: int
    cycle: int
    guesser_id: str
    giver_ids: tuple[str, str]
    word: Word
    round_deadline: float | None
    clue_deadline: float | None
    phase: Literal["clueing", "guessing", "over"] = "clueing"
    clues: list[Clue] = field(default_factory=list)
    giver_turn: int = 0
    frozen_remaining: float = 0.0
    buzzer_id: str | None = None
    guess_deadline: float | None = None
    guesses: list[dict[str, Any]] = field(default_factory=list)
    outcome: Literal["correct", "timeout", "skipped"] | None = None
    points: Counter = field(default_factory=Counter)

    @property
    def participants(self) -> tuple[str, str, str]:
        return (self.guesser_id, *self.giver_ids)

    @property
    def current_giver_id(self) -> str:
        return self.giver_ids[self.giver_turn]


@dataclass
class Match:
    settings: Settings
    participants: list[str]
    scores: Counter
    cycle: int = 0
    guesser_queue: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    clue_counts: Counter = field(default_factory=Counter)
    used_words: set[str] = field(default_factory=set)
    round: Round | None = None
    rounds_played: int = 0
    phase: Literal["playing", "reveal", "paused", "podium"] = "playing"
    reveal_until: float | None = None
    wrong_buzzes: Counter = field(default_factory=Counter)
    giver_points: Counter = field(default_factory=Counter)
    fastest_guess: dict[str, int] = field(default_factory=dict)


class Lobby:
    def __init__(self, code: str, rng: random.Random | None = None, now: float = 0.0):
        self.code = code
        self.rng = rng or random.Random()
        self.players: dict[str, Player] = {}
        self.host_id: str | None = None
        self.settings = Settings()
        self.custom_words: list[Word] = []
        self.match: Match | None = None
        self.version = 0
        self.last_active = now

    # --- Players ---------------------------------------------------------------

    def active_player_ids(self) -> list[str]:
        return [p.id for p in self.players.values() if not p.kicked]

    def join(self, name: str, token: str | None, now: float) -> Player:
        if token:
            for p in self.players.values():
                if p.token == token and not p.kicked:
                    p.connected, p.disconnected_at = True, None
                    if self.host_id is None or not self.players[self.host_id].connected:
                        self.host_id = p.id
                    self._touch(now)
                    return p
        name = name.strip()[:20]
        if not name:
            raise GameError("invalid_name")
        if any(p.name.lower() == name.lower() for p in self.players.values() if not p.kicked):
            raise GameError("name_taken")
        if len(self.active_player_ids()) >= MAX_PLAYERS:
            raise GameError("lobby_full")
        used = {p.color for p in self.players.values()}
        color = next((c for c in COLORS if c not in used), self.rng.choice(COLORS))
        player = Player(id=secrets.token_hex(4), token=secrets.token_urlsafe(16), name=name,
                        color=color, joined_at=now)
        self.players[player.id] = player
        if self.host_id is None:
            self.host_id = player.id
        if self.match:
            self.match.pending.append(player.id)
            self.match.scores[player.id] += 0
        self._touch(now)
        return player

    def disconnect(self, player_id: str, now: float) -> None:
        p = self.players.get(player_id)
        if not p or not p.connected:
            return
        p.connected, p.disconnected_at = False, now
        if self.host_id == player_id:
            self._reassign_host()
        self._touch(now)

    def kick(self, by: str, target: str) -> None:
        self._require_host(by)
        if target == by or target not in self.players:
            raise GameError("invalid_target")
        self.players[target].kicked = True
        self.players[target].connected = False
        self.version += 1

    def _reassign_host(self) -> None:
        candidates = sorted((p for p in self.players.values() if p.connected and not p.kicked),
                            key=lambda p: p.joined_at)
        if candidates:
            self.host_id = candidates[0].id

    def _require_host(self, player_id: str) -> None:
        if player_id != self.host_id:
            raise GameError("not_host")

    def _touch(self, now: float) -> None:
        self.version += 1
        self.last_active = now

    def any_connected(self) -> bool:
        return any(p.connected for p in self.players.values())

    # --- Lobby setup -----------------------------------------------------------

    def update_settings(self, by: str, changes: dict[str, Any]) -> None:
        self._require_host(by)
        if self.match and self.match.phase != "podium":
            raise GameError("match_in_progress")
        self.settings.update(changes)
        self.version += 1

    def add_custom_word(self, by: str, text: str) -> None:
        text = " ".join(text.split())
        lang = detect_language(text)
        if lang is None or len(text) > 40:
            raise GameError("invalid_word")
        if any(w.text == text for w in self.custom_words):
            raise GameError("duplicate_word")
        if sum(w.author_id == by for w in self.custom_words) >= MAX_CUSTOM_WORDS_PER_PLAYER:
            raise GameError("too_many_words")
        self.custom_words.append(Word(text=text, language=lang, author_id=by))
        self.version += 1

    def remove_custom_word(self, by: str, text: str) -> None:
        self.custom_words = [w for w in self.custom_words if not (w.author_id == by and w.text == text)]
        self.version += 1

    def start_match(self, by: str, now: float) -> None:
        self._require_host(by)
        if self.match and self.match.phase != "podium":
            raise GameError("match_in_progress")
        ready = [pid for pid in self.active_player_ids() if self.players[pid].connected]
        if len(ready) < MIN_PLAYERS:
            raise GameError("not_enough_players")
        self.match = Match(settings=Settings(**vars(self.settings)), participants=ready,
                           scores=Counter({pid: 0 for pid in ready}))
        self._next_round(now)
        self._touch(now)

    def return_to_lobby(self, by: str) -> None:
        self._require_host(by)
        if self.match and self.match.phase != "podium":
            raise GameError("match_in_progress")
        self.match = None
        self.version += 1

    # --- Scheduling ------------------------------------------------------------

    def _active_participants(self, now: float) -> list[str]:
        return [pid for pid in self.match.participants if not self.players[pid].is_away(now)]

    def _start_cycle(self) -> None:
        m = self.match
        m.participants += [pid for pid in m.pending if not self.players[pid].kicked]
        m.pending = []
        m.cycle += 1
        m.guesser_queue = [pid for pid in m.participants if not self.players[pid].kicked]
        self.rng.shuffle(m.guesser_queue)

    def _next_round(self, now: float) -> None:
        m = self.match
        m.round = None
        while True:
            if not m.guesser_queue:
                if m.cycle >= m.settings.cycles:
                    m.phase = "podium"
                    return
                self._start_cycle()
            active = self._active_participants(now)
            if len(active) < MIN_PLAYERS:
                m.phase = "paused"
                return
            # Taking the first non-Away player postpones Away players' turns; when only
            # Away players remain, their turns for this Cycle are lost.
            guesser = next((pid for pid in m.guesser_queue if pid in active), None)
            if guesser is None:
                m.guesser_queue = []
                continue
            break
        m.guesser_queue.remove(guesser)
        others = [pid for pid in active if pid != guesser]
        self.rng.shuffle(others)
        # Fewest clue-giving turns first; on a tie prefer players who still have a Guesser
        # turn ahead, since that turn is a Round they can't give clues in.
        givers = sorted(others, key=lambda pid: (m.clue_counts[pid], pid not in m.guesser_queue))[:2]
        word = self._pick_word(guesser)
        if word is None:
            m.phase = "podium"
            return
        m.used_words.add(word.text)
        for g in givers:
            m.clue_counts[g] += 1
        m.rounds_played += 1
        online = m.settings.play_mode == "online"
        m.round = Round(
            number=m.rounds_played, cycle=m.cycle, guesser_id=guesser,
            giver_ids=(givers[0], givers[1]), word=word,
            round_deadline=now + m.settings.round_seconds,
            clue_deadline=now + m.settings.clue_seconds if online else None,
        )
        m.phase = "playing"
        m.reveal_until = None

    def _pick_word(self, guesser: str) -> Word | None:
        m = self.match
        lang = m.settings.word_language
        bank = [w for w in word_bank(lang) if w.text not in m.used_words]
        custom = [w for w in self.custom_words
                  if w.language == lang and w.author_id != guesser and w.text not in m.used_words]
        source = m.settings.word_source
        pool = bank if source == "bank" else bank + custom if source == "mixed" else custom or bank
        return self.rng.choice(pool) if pool else None

    # --- Round actions ---------------------------------------------------------

    def _round_for(self, player_id: str) -> Round:
        m = self.match
        if not m or m.phase != "playing" or not m.round:
            raise GameError("no_round")
        if player_id not in m.round.participants:
            raise GameError("not_in_round")
        return m.round

    def _clue_for(self, player_id: str) -> Round:
        r = self._round_for(player_id)
        if self.match.settings.play_mode != "online":
            raise GameError("in_person_mode")
        if r.phase != "clueing":
            raise GameError("not_clueing")
        if player_id != r.current_giver_id:
            raise GameError("not_your_turn")
        return r

    def submit_clue(self, player_id: str, text: str, now: float) -> None:
        r = self._clue_for(player_id)
        try:
            clue = validate_clue(text, self.match.settings.word_language, r.word.text)
        except ClueRejected as e:
            raise GameError(e.reason) from None
        r.clues.append(Clue(player_id, clue))
        self._pass_turn(r, now)
        self._touch(now)

    def preview_spoken_clue(self, player_id: str, transcript: str) -> str:
        """Cut a speech transcript to one syllable and check it, without submitting."""
        r = self._clue_for(player_id)
        lang = self.match.settings.word_language
        syllable = first_syllable(transcript, lang)
        if syllable is None:
            raise GameError("empty")
        try:
            return validate_clue(syllable, lang, r.word.text)
        except ClueRejected as e:
            raise GameError(e.reason) from None

    def _pass_turn(self, r: Round, now: float) -> None:
        r.giver_turn = 1 - r.giver_turn
        r.clue_deadline = now + self.match.settings.clue_seconds

    def buzz(self, player_id: str, now: float) -> None:
        r = self._round_for(player_id)
        if r.phase != "clueing":
            raise GameError("not_clueing")
        r.phase = "guessing"
        r.buzzer_id = player_id
        r.frozen_remaining = max(0.0, r.round_deadline - now)
        r.round_deadline = None
        r.clue_deadline = None
        r.guess_deadline = now + GUESS_SECONDS
        self._touch(now)

    def submit_guess(self, player_id: str, text: str, now: float) -> None:
        r = self._round_for(player_id)
        if player_id != r.guesser_id:
            raise GameError("not_guesser")
        if r.phase != "guessing":
            raise GameError("not_guessing")
        self._resolve_guess(r, text, now)
        self._touch(now)

    def _resolve_guess(self, r: Round, text: str | None, now: float) -> None:
        m = self.match
        correct = text is not None and is_correct_guess(text, r.word)
        r.guesses.append({"text": text, "correct": correct, "buzzerId": r.buzzer_id})
        if correct:
            self._award(r, r.guesser_id, GUESSER_POINTS)
            for g in r.giver_ids:
                self._award(r, g, CLUE_GIVER_POINTS)
                m.giver_points[g] += CLUE_GIVER_POINTS
            best = m.fastest_guess.get(r.guesser_id)
            if best is None or len(r.clues) < best:
                m.fastest_guess[r.guesser_id] = len(r.clues)
            self._end_round(r, "correct", now)
            return
        self._award(r, r.guesser_id, WRONG_GUESS_PENALTY)
        if r.buzzer_id != r.guesser_id:
            self._award(r, r.buzzer_id, WRONG_GUESS_PENALTY)
        m.wrong_buzzes[r.buzzer_id] += 1
        r.phase = "clueing"
        r.buzzer_id = None
        r.guess_deadline = None
        r.round_deadline = now + r.frozen_remaining
        if m.settings.play_mode == "online":
            r.clue_deadline = now + m.settings.clue_seconds

    def _award(self, r: Round, player_id: str, points: int) -> None:
        r.points[player_id] += points
        self.match.scores[player_id] += points

    def _end_round(self, r: Round, outcome: str, now: float) -> None:
        r.phase = "over"
        r.outcome = outcome
        r.round_deadline = r.clue_deadline = r.guess_deadline = None
        self.match.phase = "reveal"
        self.match.reveal_until = now + REVEAL_SECONDS

    def _skip_round(self, r: Round, away: list[str], now: float) -> None:
        m = self.match
        for pid, pts in r.points.items():
            m.scores[pid] -= pts
            if pts > 0 and pid in r.giver_ids:
                m.giver_points[pid] -= pts
        r.points = Counter()
        if r.guesser_id in away:
            m.guesser_queue.append(r.guesser_id)  # the Guesser keeps their turn for later
        self._end_round(r, "skipped", now)

    # --- Clock -----------------------------------------------------------------

    def tick(self, now: float) -> bool:
        """Apply timeouts and Away transitions. Returns True if anything changed."""
        before = self.version
        m = self.match
        if m and m.phase == "playing" and m.round:
            r = m.round
            away = [pid for pid in r.participants if self.players[pid].is_away(now)]
            if away:
                self._skip_round(r, away, now)
            elif r.phase == "guessing" and now >= r.guess_deadline:
                self._resolve_guess(r, None, now)
            elif r.phase == "clueing" and now >= r.round_deadline:
                self._end_round(r, "timeout", now)
            elif r.phase == "clueing" and r.clue_deadline and now >= r.clue_deadline:
                self._pass_turn(r, now)
            else:
                return self._changed(before)
            self.version += 1
        elif m and m.phase == "reveal" and now >= m.reveal_until:
            self._next_round(now)
            self.version += 1
        elif m and m.phase == "paused" and len(self._active_participants(now)) >= MIN_PLAYERS:
            self._next_round(now)
            self.version += 1
        return self._changed(before)

    def _changed(self, before: int) -> bool:
        return self.version != before

    # --- Views -----------------------------------------------------------------

    def view(self, viewer_id: str, now: float) -> dict[str, Any]:
        """Everything a single player may see. The Secret Word never leaves for a Guesser."""
        m = self.match
        return {
            "code": self.code,
            "you": viewer_id,
            "hostId": self.host_id,
            "serverNow": now,
            "settings": self.settings.as_dict(),
            "players": [
                {"id": p.id, "name": p.name, "color": p.color, "connected": p.connected,
                 "away": p.is_away(now)}
                for p in sorted(self.players.values(), key=lambda p: p.joined_at) if not p.kicked
            ],
            "customWords": {
                "count": len(self.custom_words),
                "mine": [w.text for w in self.custom_words if w.author_id == viewer_id],
            },
            "match": self._match_view(viewer_id) if m else None,
        }

    def _match_view(self, viewer_id: str) -> dict[str, Any]:
        m = self.match
        r = m.round
        return {
            "phase": m.phase,
            "settings": m.settings.as_dict(),
            "cycle": m.cycle,
            "participants": m.participants,
            "pending": m.pending,
            "scores": dict(m.scores),
            "revealUntil": m.reveal_until,
            "round": self._round_view(r, viewer_id) if r else None,
            "podium": self._podium() if m.phase == "podium" else None,
        }

    def _round_view(self, r: Round, viewer_id: str) -> dict[str, Any]:
        role = ("guesser" if viewer_id == r.guesser_id
                else "clue_giver" if viewer_id in r.giver_ids else "spectator")
        show_word = role == "clue_giver" or r.phase == "over"
        return {
            "number": r.number,
            "cycle": r.cycle,
            "role": role,
            "guesserId": r.guesser_id,
            "giverIds": list(r.giver_ids),
            "currentGiverId": r.current_giver_id,
            "phase": r.phase,
            "word": r.word.text if show_word else None,
            "clues": [{"playerId": c.player_id, "text": c.text} for c in r.clues],
            "roundDeadline": r.round_deadline,
            "frozenRemaining": r.frozen_remaining,
            "clueDeadline": r.clue_deadline,
            "guessDeadline": r.guess_deadline,
            "buzzerId": r.buzzer_id,
            "guesses": r.guesses,
            "outcome": r.outcome,
            "points": dict(r.points),
        }

    def _podium(self) -> dict[str, Any]:
        m = self.match
        ordered = sorted(m.scores.items(), key=lambda kv: -kv[1])
        ranking, rank = [], 0
        for i, (pid, score) in enumerate(ordered):
            if i == 0 or score != ordered[i - 1][1]:
                rank = i + 1
            ranking.append({"playerId": pid, "score": score, "rank": rank})
        awards = []
        if m.fastest_guess:
            pid = min(m.fastest_guess, key=m.fastest_guess.get)
            awards.append({"id": "fastest_guess", "playerId": pid, "value": m.fastest_guess[pid]})
        if m.wrong_buzzes:
            pid, n = m.wrong_buzzes.most_common(1)[0]
            awards.append({"id": "wild_buzzer", "playerId": pid, "value": n})
        if m.giver_points:
            pid, n = m.giver_points.most_common(1)[0]
            if n > 0:
                awards.append({"id": "best_clue_giver", "playerId": pid, "value": n})
        return {"ranking": ranking, "awards": awards}


def new_lobby_code(taken: set[str], rng: random.Random | None = None) -> str:
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1L")
    rng = rng or random.SystemRandom()
    while True:
        code = "".join(rng.choice(alphabet) for _ in range(4))
        if code not in taken:
            return code
