import pytest

from partygame.clues import ClueRejected, first_syllable, validate_clue


@pytest.mark.parametrize("clue", ["งวง", "ใหญ่", "สัตว์", " มี "])
def test_thai_single_syllable_is_accepted(clue):
    assert validate_clue(clue, "th", "ช้าง") == clue.strip()


@pytest.mark.parametrize("clue", ["มะม่วง", "กิน ข้าว", "สัปดาห์"])
def test_thai_multi_syllable_is_rejected(clue):
    with pytest.raises(ClueRejected) as e:
        validate_clue(clue, "th", "ช้าง")
    assert e.value.reason == "not_one_syllable"


def test_thai_syllable_of_secret_word_is_forbidden():
    with pytest.raises(ClueRejected) as e:
        validate_clue("กระ", "th", "หมูกระทะ")
    assert e.value.reason == "forbidden_syllable"


def test_whole_secret_word_is_forbidden():
    with pytest.raises(ClueRejected) as e:
        validate_clue("ช้าง", "th", "ช้าง")
    assert e.value.reason == "forbidden_syllable"


def test_wrong_script_is_rejected():
    with pytest.raises(ClueRejected) as e:
        validate_clue("big", "th", "ช้าง")
    assert e.value.reason == "wrong_language"


def test_empty_clue_is_rejected():
    with pytest.raises(ClueRejected) as e:
        validate_clue("   ", "th", "ช้าง")
    assert e.value.reason == "empty"


@pytest.mark.parametrize("clue", ["big", "Grey", "trunk", "zorp"])
def test_english_single_syllable_is_accepted(clue):
    assert validate_clue(clue, "en", "elephant") == clue.strip().lower()


@pytest.mark.parametrize("clue", ["table", "animal", "big grey"])
def test_english_multi_syllable_is_rejected(clue):
    with pytest.raises(ClueRejected) as e:
        validate_clue(clue, "en", "elephant")
    assert e.value.reason == "not_one_syllable"


def test_english_word_inside_secret_is_forbidden():
    with pytest.raises(ClueRejected) as e:
        validate_clue("cream", "en", "ice cream")
    assert e.value.reason == "forbidden_syllable"


def test_first_syllable_of_thai_speech():
    assert first_syllable("มะม่วงสุก", "th") == "มะ"


def test_first_syllable_of_english_speech():
    assert first_syllable("Big animal", "en") == "big"


def test_first_syllable_of_nothing_is_none():
    assert first_syllable("  ", "th") is None
