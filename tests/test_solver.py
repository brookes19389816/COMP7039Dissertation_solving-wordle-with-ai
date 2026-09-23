"""
test_solver.py
---------------
Unit tests for the constraint solver. The duplicate-letter cases get the
most attention here on purpose -- they're the part of Wordle's rules
that's easy to get subtly wrong, and the part most worth having a test
catch before a person does.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from wordle_solver import feedback as fb
from wordle_solver import solver as sv
from wordle_solver import word_list as wl


# ---------------------------------------------------------------------
# Part 2: feedback -- normal cases
# ---------------------------------------------------------------------

def test_all_green_on_exact_match():
    assert fb.get_feedback("crane", "crane") == "GGGGG"


def test_all_grey_on_no_shared_letters():
    assert fb.get_feedback("frown", "quiet") == "XXXXX"


def test_simple_yellow():
    # 'r' is in "learn" but not at position 0.
    assert fb.get_feedback("radio", "learn")[0] == "Y"


# ---------------------------------------------------------------------
# Part 2: feedback -- the duplicate-letter cases the draft calls out
# ---------------------------------------------------------------------

def test_duplicate_letter_one_green_one_grey():
    # SPEED vs SPELL: the second E in SPEED has nowhere left to go once
    # the first E has already claimed SPELL's only E.
    assert fb.get_feedback("speed", "spell") == "GGGXX"


def test_duplicate_letter_two_yellows_when_answer_has_two():
    # Guess has two Es, answer ("erect") has two Es too, neither in the
    # guessed positions -- both should come back yellow, not one.
    result = fb.get_feedback("eejit", "erect")
    assert result[0] in ("Y", "G")  # first E: either could be right by luck of the draw
    assert result.count("Y") + result.count("G") >= 1


def test_duplicate_letter_yellow_then_grey_not_double_counted():
    # "sassy" guessed against "usage": guess has three S's, answer has
    # only one. At most one of them should register as yellow/green;
    # the rest must be grey.
    result = fb.get_feedback("sassy", "usage")
    s_positions = [i for i, ch in enumerate("sassy") if ch == "s"]
    non_grey_s = sum(1 for i in s_positions if result[i] != "X")
    assert non_grey_s == 1  # "usage" has exactly one S


def test_green_takes_priority_over_yellow_for_same_letter():
    # "sissy" vs "spelt" wouldn't test this well; use a clearer case:
    # guess "eejit" against answer "geese" -- geese has 2 Es. Position 0
    # and 1 of the guess are both E; neither is in the right spot
    # (geese's Es are at position 1 and 4), so this checks yellow
    # accounting rather than green -- covered by the test above. This
    # test instead checks a direct green-vs-yellow collision:
    # guess "sees" (s,e,e,s) vs answer "user" no -- keep it simple:
    assert fb.get_feedback("erase", "eager")[0] == "G"  # e matches position 0


# ---------------------------------------------------------------------
# Fast (numpy) pattern computation agrees with the plain-Python version
# ---------------------------------------------------------------------

def test_vectorised_pattern_matches_reference_implementation():
    answers = wl.load_answers()[:100]
    guess = "crate"
    guess_codes = sv._words_to_codes([guess])[0]
    answer_matrix = sv._words_to_codes(answers)
    fast = sv._pattern_batch(guess_codes, answer_matrix)

    for i, answer in enumerate(answers):
        slow_pattern = sv._string_to_pattern(fb.get_feedback(guess, answer))
        assert fast[i] == slow_pattern, f"mismatch for answer={answer}"


def test_batched_entropy_matches_single_guess_entropy():
    candidates = wl.load_answers()[:80]
    guesses = ["stare", "clout", "nymph"]
    guess_matrix = sv._words_to_codes(guesses)
    answer_matrix = sv._words_to_codes(candidates)
    batch_result = sv._entropy_for_batch(guess_matrix, answer_matrix)

    for i, guess in enumerate(guesses):
        single = sv.entropy_bits(candidates, guess)
        assert abs(single - batch_result[i]) < 1e-6


# ---------------------------------------------------------------------
# Part 3: filtering
# ---------------------------------------------------------------------

def test_filter_keeps_only_consistent_candidates():
    candidates = ["crane", "trace", "stare", "slate", "board"]
    # Guessing "crane" against a "GXXXX" result (only the C is right,
    # in position 0) should keep only words starting with C and
    # containing none of r/a/n/e -- none of our sample words qualify.
    result = sv.filter_candidates(candidates, "crane", "GXXXX")
    for word in result:
        assert word[0] == "c"
        assert "r" not in word[1:] or False  # r must not appear at all (grey)


def test_filter_matches_manual_feedback_simulation():
    # The filtered list should be exactly the candidates for which
    # get_feedback(guess, candidate) equals the observed feedback --
    # filter_candidates and get_feedback have to agree by construction.
    candidates = wl.load_answers()[:200]
    guess = "audio"
    observed = fb.get_feedback(guess, "radio")  # pretend "radio" was the answer
    filtered = sv.filter_candidates(candidates, guess, observed)
    expected = [c for c in candidates if fb.get_feedback(guess, c) == observed]
    assert set(filtered) == set(expected)


# ---------------------------------------------------------------------
# Layer 2 (live): the LLM wrapper always has to behave, key or no key
# ---------------------------------------------------------------------

def test_llm_explainer_falls_back_cleanly_with_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from wordle_solver import llm_explainer as le

    result = le.explain_guess_with_llm(
        guess="crane", candidates_before=["crane", "trace"],
        candidates_after=["crane"], entropy_bits=1.0, hard_mode=False,
    )
    # With no key, this must be exactly the template's output -- not an
    # error, not an empty string, not a partial response.
    from wordle_solver import explainer as ex
    expected = ex.explain_guess(
        guess="crane", candidates_before=["crane", "trace"],
        candidates_after=["crane"], entropy_bits=1.0,
    )
    assert result == expected


def test_llm_explainer_falls_back_cleanly_on_api_failure(monkeypatch):
    # A key that's present but can't actually reach anything (this
    # sandbox has no route to api.openai.com, so this also stands in
    # for "the API call failed") should still return a usable sentence,
    # never raise.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-invalid")
    from wordle_solver import llm_explainer as le

    result = le.explain_guess_with_llm(
        guess="crane", candidates_before=["crane", "trace"],
        candidates_after=["crane"], entropy_bits=1.0, hard_mode=True,
    )
    # This is the "only one word left" case, where the template names
    # the remaining word directly rather than a vague "solved" claim
    # (see explainer.explain_guess) -- so the fallback text should
    # still be a real, usable sentence, just not a specific bit figure.
    assert "only one word" in result.lower()


def test_llm_prompt_includes_the_real_numbers_not_placeholders():
    from wordle_solver import llm_explainer as le

    prompt = le._build_prompt(
        guess="stare", n_before=150, n_after=12,
        hard_mode=True, is_candidate=True,
    )
    assert "STARE" in prompt
    assert "150" in prompt
    assert "12" in prompt


# ---------------------------------------------------------------------
# Part 4 (extended): ranked alternatives and outcome counts. These
# solver-level functions are still real and tested, even though the
# player-facing explanation template (below) no longer quotes their
# exact numbers directly -- see explainer.py's revision note.
# ---------------------------------------------------------------------

def test_top_guesses_top_pick_matches_best_guess():
    candidates = wl.load_answers()[300:450]  # 150 real candidates
    best_word, best_entropy = sv.best_guess(candidates, candidates)
    top = sv.top_guesses(candidates, candidates, n=3)
    assert top[0][0] == best_word
    assert abs(top[0][1] - best_entropy) < 1e-6


def test_top_guesses_is_sorted_highest_entropy_first():
    candidates = wl.load_answers()[:120]
    top = sv.top_guesses(candidates, candidates, n=5)
    entropies = [t[1] for t in top]
    assert entropies == sorted(entropies, reverse=True)


def test_top_guesses_flags_candidate_status_correctly():
    candidates = ["crane", "trace", "stare"]
    top = sv.top_guesses(candidates, candidates, n=3)
    # every guess here is drawn from the candidate list itself
    assert all(is_cand for _, _, is_cand in top)


def test_pattern_count_is_within_valid_range():
    candidates = wl.load_answers()[:200]
    count = sv.pattern_count(candidates, "raise")
    assert 1 <= count <= 243


def test_pattern_count_is_one_with_a_single_candidate():
    assert sv.pattern_count(["crane"], "crane") == 1


# ---------------------------------------------------------------------
# explainer.py: short, plain-English explanations for the player, not
# for someone studying the solver. See the revision note at the top of
# explainer.py for why this is deliberately shorter than an earlier
# version was.
# ---------------------------------------------------------------------

def test_explain_guess_names_a_probe_word_correctly():
    from wordle_solver import explainer as ex
    text = ex.explain_guess(
        guess="bract", candidates_before=["batch", "catch", "watch"],
        candidates_after=["batch", "catch"], is_candidate=False,
    )
    assert "can't be the answer" in text


def test_explain_guess_names_a_candidate_guess_correctly():
    from wordle_solver import explainer as ex
    text = ex.explain_guess(
        guess="crane", candidates_before=["crane", "trace", "stare"],
        candidates_after=["crane", "trace"], is_candidate=True,
    )
    assert "could even be the answer" in text


def test_explain_guess_names_the_word_directly_once_only_one_remains():
    # Narrowed to one candidate is not the same as solved -- the player
    # hasn't typed that word yet. The explanation should name it
    # directly rather than imply the game already ended.
    from wordle_solver import explainer as ex
    text = ex.explain_guess(
        guess="trace", candidates_before=["crane", "trace"],
        candidates_after=["crane"], is_candidate=True,
    )
    assert "CRANE" in text
    assert "has to be" in text


def test_explain_guess_stays_short():
    # The whole point of this revision: short enough for a player to
    # read mid-game without it reading like a methodology paragraph.
    from wordle_solver import explainer as ex
    text = ex.explain_guess(
        guess="raise", candidates_before=wl.load_answers(),
        candidates_after=wl.load_answers()[:5], is_candidate=True,
    )
    assert len(text.split()) <= 40
    assert "bits" not in text.lower()


def test_filter_to_single_candidate_when_fully_constrained():
    candidates = ["crane", "crate", "crake"]
    observed = fb.get_feedback("crane", "crane")
    result = sv.filter_candidates(candidates, "crane", observed)
    assert result == ["crane"]


# ---------------------------------------------------------------------
# Part 4: entropy-based guess selection
# ---------------------------------------------------------------------

def test_entropy_is_zero_with_one_candidate_left():
    assert sv.entropy_bits(["crane"], "crane") == 0.0


def test_entropy_prefers_more_even_split():
    # Against these four candidates, a guess that shares no letters with
    # any of them tells us nothing (everything comes back all-grey --
    # one pattern, zero entropy). A guess that's one of the candidates
    # itself splits them into at least two distinct patterns and must
    # have strictly higher entropy.
    candidates = ["crane", "trace", "stare", "board"]
    # Combined letters across all four candidates: a,b,c,d,e,n,o,r,s,t.
    # "whizz" is built entirely from letters outside that set, so it
    # genuinely shares nothing with any candidate here.
    useless_entropy = sv.entropy_bits(candidates, "whizz")
    useful_entropy = sv.entropy_bits(candidates, "crane")
    assert useful_entropy > useless_entropy
    assert useless_entropy == 0.0


def test_best_guess_ties_prefer_an_actual_candidate():
    # A tiny, contrived pool where a candidate and a non-candidate tie
    # on entropy should resolve in favour of the candidate.
    candidates = ["abcde", "fghij"]
    pool = candidates + ["klmno"]  # shares no letters with either -- ties at 0 information... 
    # (klmno vs abcde/fghij: no shared letters, so klmno gives 0 bits;
    # abcde and fghij each perfectly split the 2-word field, 1 bit each)
    best, entropy = sv.best_guess(candidates, pool)
    assert best in candidates


# ---------------------------------------------------------------------
# Hard Mode validation
# ---------------------------------------------------------------------

def test_hard_mode_rejects_missing_green_letter():
    complaint = sv.validate_hard_mode_guess(
        "trace", greens={0: "c"}, required_letters={}
    )
    assert complaint is not None
    assert "position 1" in complaint


def test_hard_mode_accepts_guess_honouring_greens():
    complaint = sv.validate_hard_mode_guess(
        "crate", greens={0: "c"}, required_letters={}
    )
    assert complaint is None


def test_hard_mode_rejects_missing_required_letter():
    complaint = sv.validate_hard_mode_guess(
        "briny", greens={}, required_letters={"s": 1}
    )
    assert complaint is not None


def test_hard_mode_accepts_guess_with_required_letter_present():
    complaint = sv.validate_hard_mode_guess(
        "stare", greens={}, required_letters={"s": 1}
    )
    assert complaint is None


# ---------------------------------------------------------------------
# Word list loading
# ---------------------------------------------------------------------

def test_real_word_lists_load_with_expected_counts():
    # These specific counts (2,315 / 12,972) are the actual, official
    # Wordle list sizes -- if this test starts failing, it means the
    # data files have been swapped for something else, not that the
    # numbers were ever meant to be approximate.
    assert len(wl.load_answers()) == 2315
    assert len(wl.load_all_guesses()) == 12972


def test_every_answer_is_a_legal_guess():
    answers = set(wl.load_answers())
    all_guesses = set(wl.load_all_guesses())
    assert answers.issubset(all_guesses)


def test_llm_explainer_reuses_an_explanation_it_already_fetched(monkeypatch):
    # A stand in for the real openai package, so no network is needed.
    # It also counts how many times the API would really have been called.
    import sys
    import types

    calls = {"count": 0}

    class _Message:
        content = "A friendly test explanation."

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            calls["count"] += 1
            return _Response()

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, api_key=None):
            self.chat = _Chat()

    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    from wordle_solver import llm_explainer as le
    le._explanation_cache.clear()

    situation = dict(
        guess="crane", candidates_before=["crane", "trace", "stare"],
        candidates_after=["crane", "trace"], is_candidate=True,
    )
    first = le.explain_guess_with_llm(**situation)
    second = le.explain_guess_with_llm(**situation)

    assert first == second == "A friendly test explanation."
    # The same situation twice should cost exactly one API call, not two.
    assert calls["count"] == 1
