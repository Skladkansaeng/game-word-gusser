import random

import pytest

from partygame.game import (
    AWAY_GRACE_SECONDS,
    BUZZ_LOCK_SECONDS,
    GUESS_SECONDS,
    REVEAL_SECONDS,
    Clue,
    GameError,
    Lobby,
)
from partygame.words import Word

T0 = 1000.0


def make_lobby(n=3, seed=1, **settings):
    lobby = Lobby("ABCD", rng=random.Random(seed), now=T0)
    players = [lobby.join(f"p{i}", None, T0).id for i in range(n)]
    if settings:
        lobby.update_settings(players[0], settings)
    return lobby, players


def start(lobby, players):
    for p in players:
        lobby.set_ready(p, True)
    lobby.start_match(players[0], T0)


def started(n=3, seed=1, **settings):
    lobby, players = make_lobby(n, seed, **settings)
    start(lobby, players)
    return lobby, players


def roles(lobby):
    r = lobby.match.round
    return r.guesser_id, r.giver_ids


def finish_reveal(lobby, now):
    lobby.tick(now + REVEAL_SECONDS + 0.01)
    return now + REVEAL_SECONDS + 0.01


def win_round(lobby, now):
    guesser, _ = roles(lobby)
    lobby.buzz(guesser, now)
    lobby.submit_guess(guesser, lobby.match.round.word.text, now)


# --- Lobby -------------------------------------------------------------------


def test_first_player_is_host():
    lobby, players = make_lobby(3)
    assert lobby.host_id == players[0]


def test_duplicate_name_is_rejected():
    lobby, _ = make_lobby(1)
    with pytest.raises(GameError, match="name_taken"):
        lobby.join("p0", None, T0)


def test_lobby_is_capped_at_twelve():
    lobby, _ = make_lobby(12)
    with pytest.raises(GameError, match="lobby_full"):
        lobby.join("extra", None, T0)


def test_rejoining_with_token_restores_the_same_player():
    lobby, players = make_lobby(3)
    token = lobby.players[players[1]].token
    lobby.disconnect(players[1], T0)
    again = lobby.join("whatever", token, T0 + 1)
    assert again.id == players[1] and again.connected


def test_only_host_can_start_and_needs_three_players():
    lobby, players = make_lobby(2)
    with pytest.raises(GameError, match="not_enough_players"):
        lobby.start_match(players[0], T0)
    lobby.join("p2", None, T0)
    with pytest.raises(GameError, match="not_host"):
        lobby.start_match(players[1], T0)


def test_everyone_but_the_host_must_be_ready_to_start():
    lobby, players = make_lobby(3)
    lobby.set_ready(players[1], True)
    assert [p["ready"] for p in lobby.view(players[0], T0)["players"]] == [True, True, False]
    with pytest.raises(GameError, match="players_not_ready"):
        lobby.start_match(players[0], T0)
    lobby.set_ready(players[2], True)
    lobby.start_match(players[0], T0)
    assert not any(p.ready for p in lobby.players.values())
    with pytest.raises(GameError, match="match_in_progress"):
        lobby.set_ready(players[1], False)


def test_cannot_ready_without_a_custom_word_when_source_is_custom():
    lobby, players = make_lobby(3, word_source="custom")
    with pytest.raises(GameError, match="missing_custom_words"):
        lobby.set_ready(players[1], True)
    lobby.add_custom_word(players[1], "หมูเด้ง")
    lobby.set_ready(players[1], True)
    assert lobby.players[players[1]].ready


def test_offline_players_do_not_block_ready():
    lobby, players = make_lobby(4)
    for p in players[1:3]:
        lobby.set_ready(p, True)
    lobby.disconnect(players[3], T0)
    lobby.start_match(players[0], T0)
    assert lobby.match.participants == players[:3]


def test_host_moves_to_longest_present_player_on_disconnect():
    lobby, players = make_lobby(3)
    lobby.disconnect(players[0], T0)
    assert lobby.host_id == players[1]


def test_host_can_kick():
    lobby, players = make_lobby(4)
    lobby.kick(players[0], players[3])
    assert players[3] not in lobby.active_player_ids()


# --- Round flow --------------------------------------------------------------


def test_round_has_one_guesser_and_two_distinct_clue_givers():
    lobby, players = started(3)
    guesser, givers = roles(lobby)
    assert len({guesser, *givers}) == 3


def test_host_sets_how_many_players_each_round_has():
    lobby, _ = started(6, round_players=4)
    guesser, givers = roles(lobby)
    assert len(givers) == 3 and len({guesser, *givers}) == 4


def test_round_uses_everyone_when_fewer_players_than_round_size():
    lobby, _ = started(3, round_players=5)
    assert len(roles(lobby)[1]) == 2


def test_round_size_must_be_in_range():
    lobby, players = make_lobby(3)
    with pytest.raises(GameError, match="invalid_setting"):
        lobby.update_settings(players[0], {"roundPlayers": 2})


def test_clue_givers_take_turns_in_order():
    lobby, _ = started(5, round_players=4)
    r = lobby.match.round
    order = []
    for i in range(4):
        order.append(r.current_giver_id)
        lobby.submit_clue(r.current_giver_id, ["หมู", "ไก่", "ปลา", "นก"][i], T0 + 1 + i)
    assert order[:3] == list(r.giver_ids) and order[3] == r.giver_ids[0]


def test_guesser_cannot_see_secret_word_but_clue_giver_can():
    lobby, players = started(4)
    guesser, givers = roles(lobby)
    spectator = next(p for p in players if p not in (guesser, *givers))
    word = lobby.match.round.word.text
    assert lobby.view(guesser, T0)["match"]["round"]["word"] is None
    assert lobby.view(spectator, T0)["match"]["round"]["word"] is None
    assert lobby.view(givers[0], T0)["match"]["round"]["word"] == word


def test_clue_givers_alternate():
    lobby, _ = started(3)
    r = lobby.match.round
    r.word = Word("ช้าง", "th")
    first, second = r.giver_ids
    lobby.submit_clue(first, "งวง", T0 + 1)
    with pytest.raises(GameError, match="not_your_turn"):
        lobby.submit_clue(first, "ใหญ่", T0 + 2)
    lobby.submit_clue(second, "ใหญ่", T0 + 2)
    assert [c.text for c in r.clues] == ["งวง", "ใหญ่"]


def test_invalid_clue_is_rejected_with_reason():
    lobby, _ = started(3)
    r = lobby.match.round
    r.word = Word("หมูกระทะ", "th")
    with pytest.raises(GameError, match="forbidden_syllable"):
        lobby.submit_clue(r.giver_ids[0], "หมู", T0 + 1)
    assert r.clues == []


def test_clue_timer_passes_the_turn():
    lobby, _ = started(3, clue_seconds=10)
    r = lobby.match.round
    first, second = r.giver_ids
    lobby.tick(T0 + 10.01)
    assert r.current_giver_id == second


def test_clue_giver_who_runs_out_of_clue_time_loses_a_point():
    lobby, _ = started(3, clue_seconds=10)
    first, second = lobby.match.round.giver_ids
    lobby.tick(T0 + 10.01)
    lobby.tick(T0 + 20.02)
    lobby.tick(T0 + 30.03)
    assert lobby.match.scores[first] == -2 and lobby.match.scores[second] == -1


def test_correct_guess_scores_three_and_one_each():
    lobby, _ = started(3)
    guesser, givers = roles(lobby)
    win_round(lobby, T0 + 5)
    scores = lobby.match.scores
    assert scores[guesser] == 3 and all(scores[g] == 1 for g in givers)
    assert lobby.match.phase == "reveal"


def test_clue_giver_can_buzz_but_only_guesser_guesses():
    lobby, _ = started(3)
    guesser, givers = roles(lobby)
    lobby.buzz(givers[0], T0 + 1)
    with pytest.raises(GameError, match="not_guesser"):
        lobby.submit_guess(givers[0], "x", T0 + 2)


def test_answer_inside_a_sentence_wins_the_round():
    lobby, _ = started(3)
    guesser, _ = roles(lobby)
    r = lobby.match.round
    lobby.buzz(guesser, T0 + 1)
    lobby.submit_guess(guesser, f"คิดว่าเป็น {r.word.text} แน่ ๆ", T0 + 2)
    assert r.outcome == "correct"
    assert lobby.match.scores[guesser] == 3


def test_close_guess_is_wrong_but_flagged_with_matched_syllables():
    lobby, _ = started(3)
    guesser, _ = roles(lobby)
    r = lobby.match.round
    r.word = Word("จิงโจ้", "th")
    lobby.buzz(guesser, T0 + 1)
    lobby.submit_guess(guesser, "จิงโจ", T0 + 2)
    assert r.phase == "clueing"
    assert r.guesses[-1] | {"buzzerId": None} == {
        "text": "จิงโจ", "correct": False, "close": True, "matched": ["จิง"], "buzzerId": None}
    assert lobby.match.scores[guesser] == -1


def test_wrong_guess_penalises_guesser_and_buzzer_and_play_continues():
    lobby, _ = started(3)
    guesser, givers = roles(lobby)
    lobby.buzz(givers[1], T0 + 1)
    lobby.submit_guess(guesser, "ผิดแน่นอน", T0 + 2)
    scores = lobby.match.scores
    assert scores[guesser] == -1 and scores[givers[1]] == -1 and scores[givers[0]] == 0
    assert lobby.match.round.phase == "clueing"


def test_guesser_buzzing_wrong_loses_only_one_point():
    lobby, _ = started(3)
    guesser, _ = roles(lobby)
    lobby.buzz(guesser, T0 + 1)
    lobby.submit_guess(guesser, "ผิดแน่นอน", T0 + 2)
    assert lobby.match.scores[guesser] == -1


def test_repeated_wrong_buzzes_cost_more_each_time():
    lobby, _ = started(3)
    guesser, givers = roles(lobby)
    now = T0 + 1
    for _ in range(3):
        lobby.buzz(givers[0], now)
        lobby.submit_guess(guesser, "ผิดแน่นอน", now + 1)
        now += BUZZ_LOCK_SECONDS + 1
    scores = lobby.match.scores
    assert scores[givers[0]] == -1 - 2 - 3
    assert scores[guesser] == -3  # the Guesser didn't choose to buzz, so stays at -1 each


def test_wrong_buzz_locks_the_buzzer_for_a_moment():
    lobby, _ = started(3)
    guesser, givers = roles(lobby)
    lobby.buzz(givers[0], T0 + 1)
    lobby.submit_guess(guesser, "ผิดแน่นอน", T0 + 2)
    with pytest.raises(GameError, match="buzz_locked"):
        lobby.buzz(givers[0], T0 + 3)
    lobby.buzz(givers[1], T0 + 3)  # everyone else can still buzz
    assert lobby.match.round.buzzer_id == givers[1]


def test_spectator_cannot_buzz():
    lobby, players = started(4)
    guesser, givers = roles(lobby)
    spectator = next(p for p in players if p not in (guesser, *givers))
    with pytest.raises(GameError, match="not_in_round"):
        lobby.buzz(spectator, T0 + 1)


def test_round_timer_freezes_while_guessing():
    lobby, _ = started(3, round_seconds=30)
    guesser, _ = roles(lobby)
    lobby.buzz(guesser, T0 + 25)
    lobby.tick(T0 + 40)  # past the original deadline, but within the guess window
    assert lobby.match.round.phase == "guessing"
    lobby.submit_guess(guesser, "ผิดแน่นอน", T0 + 40)
    lobby.tick(T0 + 44)  # 5 seconds were left on the clock
    assert lobby.match.round.phase == "clueing"
    lobby.tick(T0 + 45.01)
    assert lobby.match.round.outcome == "timeout"


def test_guess_timeout_counts_as_wrong_guess():
    lobby, _ = started(3)
    guesser, givers = roles(lobby)
    lobby.buzz(givers[0], T0 + 1)
    lobby.tick(T0 + 1 + GUESS_SECONDS + 0.01)
    assert lobby.match.scores[guesser] == -1 and lobby.match.scores[givers[0]] == -1


def test_round_timeout_scores_nothing():
    lobby, _ = started(3, round_seconds=30)
    lobby.tick(T0 + 30.01)
    assert lobby.match.round.outcome == "timeout"
    assert all(v == 0 for v in lobby.match.scores.values())


# --- Cycles and scheduling ---------------------------------------------------


def play_out(lobby, now):
    """Win every round until the Podium; returns the guesser of each round."""
    guessers = []
    while lobby.match.phase != "podium":
        guessers.append(roles(lobby)[0])
        win_round(lobby, now)
        now = finish_reveal(lobby, now)
    return guessers


def test_every_player_guesses_exactly_once_per_cycle():
    lobby, players = started(5, cycles=2)
    guessers = play_out(lobby, T0)
    assert len(guessers) == 10
    assert sorted(guessers[:5]) == sorted(players) and sorted(guessers[5:]) == sorted(players)


def test_clue_giving_is_spread_evenly():
    lobby, players = started(5, cycles=2)
    play_out(lobby, T0)
    counts = lobby.match.clue_counts
    assert max(counts.values()) - min(counts.values()) <= 1


def test_secret_words_do_not_repeat_within_a_match():
    lobby, _ = started(6, cycles=3)
    words = []
    now = T0
    while lobby.match.phase != "podium":
        words.append(lobby.match.round.word.text)
        win_round(lobby, now)
        now = finish_reveal(lobby, now)
    assert len(words) == len(set(words)) == 18


def test_player_who_joins_mid_match_plays_from_next_cycle():
    lobby, players = started(3, cycles=2)
    late = lobby.join("late", None, T0).id
    assert late not in lobby.match.round.participants
    guessers = play_out(lobby, T0)
    assert late not in guessers[:3]
    assert guessers[3:].count(late) == 1


# --- Away ----------------------------------------------------------------------


def test_disconnect_in_round_skips_it_and_cancels_its_points():
    lobby, players = started(4)
    guesser, givers = roles(lobby)
    lobby.buzz(givers[0], T0 + 1)
    lobby.submit_guess(guesser, "ผิดแน่นอน", T0 + 2)
    lobby.disconnect(givers[1], T0 + 3)
    lobby.tick(T0 + 3 + AWAY_GRACE_SECONDS + 0.01)
    assert lobby.match.round.outcome == "skipped"
    assert all(v == 0 for v in lobby.match.scores.values())


def test_quick_reconnect_does_not_skip_the_round():
    lobby, players = started(3)
    _, givers = roles(lobby)
    token = lobby.players[givers[0]].token
    lobby.disconnect(givers[0], T0 + 1)
    lobby.join("x", token, T0 + 2)
    lobby.tick(T0 + 1 + AWAY_GRACE_SECONDS + 1)
    assert lobby.match.round.phase == "clueing"


def test_away_player_is_not_picked_and_guesser_turn_is_postponed():
    lobby, players = started(4)
    guesser, givers = roles(lobby)
    # Find someone whose guesser turn is still ahead and make them Away.
    away = lobby.match.guesser_queue[0]
    lobby.disconnect(away, T0)
    lobby.tick(T0 + AWAY_GRACE_SECONDS + 0.01)  # also skips the round if `away` was in it
    now = T0 + AWAY_GRACE_SECONDS + 0.01
    if lobby.match.phase == "reveal":
        now = finish_reveal(lobby, now)
    assert away not in lobby.match.round.participants
    lobby.join("back", lobby.players[away].token, now)
    guessers = [roles(lobby)[0]] + play_out(lobby, now)[1:]
    assert away in guessers


def test_away_guesser_who_never_returns_loses_the_turn():
    lobby, players = started(4)
    away = lobby.match.guesser_queue[0]
    lobby.disconnect(away, T0)
    now = T0 + AWAY_GRACE_SECONDS + 0.01
    lobby.tick(now)
    if lobby.match.phase == "reveal":
        now = finish_reveal(lobby, now)
    guessers = play_out(lobby, now)
    assert away not in guessers


def test_match_pauses_below_three_active_players_and_resumes():
    lobby, players = started(3)
    _, givers = roles(lobby)
    token = lobby.players[givers[0]].token
    lobby.disconnect(givers[0], T0)
    now = T0 + AWAY_GRACE_SECONDS + 0.01
    lobby.tick(now)
    now = finish_reveal(lobby, now)
    assert lobby.match.phase == "paused"
    lobby.join("x", token, now)
    lobby.tick(now + 0.1)
    assert lobby.match.phase == "playing"


# --- Custom Words --------------------------------------------------------------


def test_custom_word_is_never_given_to_its_author_as_guesser():
    lobby, players = make_lobby(3, word_source="custom")
    for p in players:
        lobby.add_custom_word(p, f"คำของ{['หนึ่ง', 'สอง', 'สาม'][players.index(p)]}")
    start(lobby, players)
    now = T0
    while lobby.match.phase != "podium":
        r = lobby.match.round
        assert r.word.author_id != r.guesser_id
        win_round(lobby, now)
        now = finish_reveal(lobby, now)


def test_custom_only_needs_a_word_from_every_player():
    lobby, players = make_lobby(3, word_source="custom")
    lobby.add_custom_word(players[0], "หมูเด้ง")
    lobby.add_custom_word(players[1], "hot dog")  # wrong language doesn't count
    assert lobby.view(players[0], T0)["customWords"]["missing"] == players[1:]
    with pytest.raises(GameError, match="missing_custom_words"):
        lobby.start_match(players[0], T0)


def test_custom_only_falls_back_to_word_bank():
    lobby, players = make_lobby(3, word_source="custom", cycles=2)
    for p, w in zip(players, ["หมูเด้ง", "น้องแมว", "ชาไทย"]):
        lobby.add_custom_word(p, w)
    start(lobby, players)
    now, words = T0, []
    while lobby.match.phase != "podium":
        words.append(lobby.match.round.word)
        win_round(lobby, now)
        now = finish_reveal(lobby, now)
    assert sum(w.is_custom for w in words) == 3 and len(words) == 6


def test_custom_word_must_match_a_known_language():
    lobby, players = make_lobby(3)
    with pytest.raises(GameError, match="invalid_word"):
        lobby.add_custom_word(players[0], "หมู dog")


def test_other_players_only_see_custom_word_count():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[0], "หมูเด้ง")
    assert lobby.view(players[1], T0)["customWords"]["mine"] == []
    assert lobby.view(players[0], T0)["customWords"]["mine"] == ["หมูเด้ง"]


# --- Podium --------------------------------------------------------------------


def test_podium_uses_shared_ranks():
    lobby, players = started(3)
    play_out(lobby, T0)
    podium = lobby.view(players[0], T0)["match"]["podium"]
    # Everyone guessed once and gave clues twice: 3 + 1 + 1 each.
    assert [row["rank"] for row in podium["ranking"]] == [1, 1, 1]
    assert {row["score"] for row in podium["ranking"]} == {5}


def test_play_again_keeps_settings_and_custom_words():
    lobby, players = started(3, cycles=1, round_seconds=45)
    lobby.add_custom_word(players[1], "หมูเด้ง")
    play_out(lobby, T0)
    lobby.return_to_lobby(players[0])
    assert lobby.match is None
    assert lobby.settings.round_seconds == 45 and len(lobby.custom_words) == 1


def test_everyone_sees_custom_word_counts_per_author():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[1], "หมูเด้ง")
    lobby.add_custom_word(players[1], "น้องแมว")
    lobby.add_custom_word(players[2], "ชาไทย")
    view = lobby.view(players[0], T0)["customWords"]
    assert view["byAuthor"] == {players[1]: 2, players[2]: 1}
    assert view["mine"] == []


def test_host_can_clear_a_players_custom_words_without_seeing_them():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[1], "หมูเด้ง")
    lobby.add_custom_word(players[2], "ชาไทย")
    lobby.clear_custom_words(players[0], players[1])
    assert [w.text for w in lobby.custom_words] == ["ชาไทย"]


def test_only_host_can_clear_custom_words():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[2], "ชาไทย")
    with pytest.raises(GameError, match="not_host"):
        lobby.clear_custom_words(players[1], players[2])


def test_host_sees_custom_word_lengths_but_never_the_words():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[1], "ก๋วยเตี๋ยว")
    lobby.add_custom_word(players[2], "หมูกระทะ")
    host_view = lobby.view(players[0], T0)["customWords"]
    assert sorted((w["syllables"], w["chars"]) for w in host_view["lengths"]) == [(2, 10), (3, 8)]
    assert "ก๋วยเตี๋ยว" not in str(host_view) and "หมูกระทะ" not in str(host_view)
    assert lobby.view(players[1], T0)["customWords"]["lengths"] is None


def test_host_can_remove_one_custom_word_by_id():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[1], "ก๋วยเตี๋ยว")
    lobby.add_custom_word(players[1], "ชาไทย")
    long_word = max(lobby.view(players[0], T0)["customWords"]["lengths"], key=lambda w: w["chars"])
    lobby.remove_custom_word_by_id(players[0], long_word["id"])
    assert [w.text for w in lobby.custom_words] == ["ชาไทย"]


def test_only_host_can_remove_by_id():
    lobby, players = make_lobby(3)
    lobby.add_custom_word(players[1], "ชาไทย")
    word_id = lobby.custom_words[0].id
    with pytest.raises(GameError, match="not_host"):
        lobby.remove_custom_word_by_id(players[2], word_id)


# --- History -------------------------------------------------------------------


def test_history_records_each_finished_round_with_clues_and_guesses():
    lobby, players = started(3)
    guesser, givers = roles(lobby)
    word = lobby.match.round.word.text
    lobby.match.round.clues.append(Clue(givers[0], "สัตว์"))
    lobby.buzz(guesser, T0 + 1)
    lobby.submit_guess(guesser, "ผิดแน่นอน", T0 + 2)
    assert lobby.history == []  # nothing until the Round is over
    win_round(lobby, T0 + 10)
    [entry] = lobby.history
    assert entry["match"] == 1 and entry["number"] == 1
    assert entry["word"] == word and entry["outcome"] == "correct"
    assert entry["guesserId"] == guesser and entry["giverIds"] == list(givers)
    assert entry["clues"] == [{"playerId": givers[0], "text": "สัตว์"}]
    assert [g["correct"] for g in entry["guesses"]] == [False, True]
    assert entry["people"][guesser]["name"] == lobby.players[guesser].name


def test_history_is_shown_to_everyone_and_survives_the_next_match():
    lobby, players = started(3)
    now = T0
    while lobby.match.phase != "podium":
        lobby.tick(now + 1000)  # every Round times out
        now = finish_reveal(lobby, now + 1000)
    lobby.return_to_lobby(players[0])
    start(lobby, players)
    lobby.tick(now + 2000)
    assert [e["match"] for e in lobby.history] == [1, 1, 1, 2]
    assert all(e["outcome"] == "timeout" for e in lobby.history)
    assert lobby.view(players[1], now)["history"] == lobby.history

