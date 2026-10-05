from partygame.words import Word, detect_language, is_correct_guess, judge_guess, word_bank


def test_exact_guess_is_correct():
    assert is_correct_guess("ช้าง", Word("ช้าง", "th"))


def test_guess_ignores_spaces_and_case():
    word = Word("ice cream", "en")
    assert is_correct_guess("  Ice Cream ", word)
    assert is_correct_guess("icecream", word)


def test_accepted_spelling_is_correct():
    assert is_correct_guess("ไอติม", Word("ไอศกรีม", "th", accepted=("ไอติม",)))


def test_repeated_thai_mark_typo_is_forgiven():
    assert is_correct_guess("ช้้าง", Word("ช้าง", "th"))


def test_wrong_guess_and_empty_guess_are_incorrect():
    word = Word("ช้าง", "th")
    assert not is_correct_guess("ม้า", word)
    assert not is_correct_guess("   ", word)


def test_answer_inside_a_sentence_is_correct():
    assert judge_guess("น่าจะเป็นช้างนะ", Word("ช้าง", "th")).verdict == "correct"
    assert judge_guess("I think it's ice cream", Word("ice cream", "en")).verdict == "correct"


def test_small_typo_is_close_not_correct_and_shows_right_syllables():
    result = judge_guess("จิงโจ", Word("จิงโจ้", "th"))
    assert result.verdict == "close"
    assert result.matched == ("จิง",)
    assert not is_correct_guess("จิงโจ", Word("จิงโจ้", "th"))


def test_guess_sharing_a_syllable_in_place_is_close():
    result = judge_guess("สนามมวย", Word("สนามบิน", "th"))
    assert result.verdict == "close"
    assert result.matched == ("สนาม",)


def test_shared_syllable_in_the_wrong_place_is_wrong():
    assert judge_guess("มวยสนาม", Word("สนามบิน", "th")).verdict == "wrong"


def test_close_english_guess_shows_right_words():
    result = judge_guess("ice creem", Word("ice cream", "en"))
    assert result.verdict == "close"
    assert result.matched == ("ice",)


def test_short_word_needs_exact_spelling():
    assert judge_guess("ม้า", Word("ช้าง", "th")).verdict == "wrong"
    assert judge_guess("cat", Word("car", "en")).verdict == "wrong"


def test_detect_language():
    assert detect_language("หมู กระทะ") == "th"
    assert detect_language("hot dog") == "en"
    assert detect_language("หมู dog") is None
    assert detect_language("  ") is None


def test_word_banks_load_and_are_unique():
    for lang in ("th", "en"):
        words = word_bank(lang)
        assert len(words) >= 100
        assert len({w.text for w in words}) == len(words)
        assert all(w.language == lang and not w.is_custom for w in words)
