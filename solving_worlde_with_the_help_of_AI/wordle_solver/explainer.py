"""
explainer.py
------------
Layer 2 of the architecture: turns one of the solver's decisions into a
plain-English sentence. This is the module the Methodology chapter calls
the "Explanation Generator".

REVISION NOTE, THIRD PASS: the second version of this template added two
genuinely new pieces of reasoning -- whether a guess could itself win,
and a precise numeric comparison against the runner-up guess it beat --
on top of the first version's plain-language verdict. On reflection, and
after further feedback, that second version explains the decision well
to someone already interested in HOW the solver works, but reads as
written for that audience rather than for the person actually playing
Wordle and wanting quick, plain help. A phrase like "would have gained
5.86 bits instead of 5.88" is precise, but it is precise in a way an
everyday player has no use for.

This version keeps the one piece of reasoning that is genuinely useful
to a normal player in plain language -- whether the suggested word could
itself be the answer, or is only a smart way of testing information --
and drops the exact bit-level comparison to a named alternative, which
belongs in this report's Methodology and Results chapters, not in the
sentence a player reads mid-game. The underlying solver functions this
template used to quote directly, solver.top_guesses and
solver.pattern_count, are unchanged and still fully tested; only how
much of what they know gets said out loud to a player has changed.

An LLM call is still worth having for turning this into a slightly more
varied, natural sentence -- but the LLM's job there is phrasing, not
deciding what to say, and it is held to the same short, plain standard
as the template below. If the API is ever unavailable, this template is
the fallback.
"""

from typing import Iterable, List, Optional


def _narrow_tier(n_before: int, n_after: int) -> str:
    """
    A short, plain word for how much a guess narrowed things down --
    the one piece of "how good was this" colour a normal player can use
    at a glance, without needing a number attached to it.
    """
    if n_before <= 1:
        return "reasonable"
    ratio = n_after / n_before
    if ratio < 0.03:
        return "great"
    if ratio < 0.15:
        return "strong"
    if ratio < 0.40:
        return "solid"
    return "reasonable"


def explain_guess(
    guess: str,
    candidates_before: Iterable,
    candidates_after: Iterable,
    entropy_bits: float = 0.0,
    is_candidate: Optional[bool] = None,
    hard_mode_constraints: Optional[List[str]] = None,
) -> str:
    """
    Turn one step of the entropy-based solver into a short, plain
    English explanation -- written for the person playing the game,
    not for someone studying how the solver works.

    Parameters
    ----------
    guess : the word the solver chose this turn
    candidates_before : candidate word list before this guess
    candidates_after  : candidate word list after applying the feedback
    entropy_bits : kept for backward compatibility with earlier callers;
                   no longer quoted directly in the player-facing text
    is_candidate : whether `guess` could itself still be the answer.
                   Omit if unknown, and that part is simply left out.
    hard_mode_constraints : optional, plain-English constraints Hard
                             Mode imposed on this turn

    Returns
    -------
    A short, plain English explanation, usually one or two sentences.
    """
    n_before, n_after = len(list(candidates_before)), len(list(candidates_after))
    guess_word = guess.upper()

    if n_after == 1:
        # Narrowed to one possibility is not the same as solved -- the
        # player hasn't typed that word yet, since a genuine win is
        # handled separately by the caller before this function is even
        # reached. Naming the word directly is clearer than a vague
        # "that's the answer" here, and more useful besides.
        only_word = list(candidates_after)[0].upper()
        text = f'Guessed "{guess_word}". Only one word now fits every clue: it has to be {only_word}.'
    else:
        tier = _narrow_tier(n_before, n_after)
        if is_candidate is True:
            text = (
                f'Guessed "{guess_word}". This could even be the answer itself, '
                f'and it\'s a {tier} pick either way: it narrowed things down '
                f'from {n_before} words to {n_after}.'
            )
        elif is_candidate is False:
            text = (
                f'Guessed "{guess_word}". This word can\'t be the answer, but '
                f'it\'s a {tier} way to narrow things down: from {n_before} '
                f'words to {n_after}.'
            )
        else:
            text = (
                f'Guessed "{guess_word}". A {tier} pick: it narrowed things '
                f'down from {n_before} words to {n_after}.'
            )

    if hard_mode_constraints:
        text += f' Hard Mode constraints applied: {"; ".join(hard_mode_constraints)}.'

    return text


# --- example: wiring into the real solver, not stand-in numbers -----------
if __name__ == "__main__":
    from . import feedback as fb
    from . import solver as sv
    from . import word_list as wl

    answers = wl.load_answers()
    candidates_before = list(answers)

    guess, entropy, is_cand = sv.top_guesses(candidates_before, candidates_before, n=1)[0]
    observed = fb.get_feedback(guess, "stare")
    candidates_after = sv.filter_candidates(candidates_before, guess, observed)

    print(explain_guess(
        guess=guess,
        candidates_before=candidates_before,
        candidates_after=candidates_after,
        is_candidate=is_cand,
    ))
    print()

    # A worked example of the "pure probe" case, where the best guess
    # can't itself be the answer, and narrows things down without
    # solving them outright.
    small_candidates = ["batch", "catch", "watch", "hatch", "latch"]
    print(explain_guess(
        guess="tench", candidates_before=small_candidates,
        candidates_after=["catch", "watch"], is_candidate=False,
    ))

    print()
    print(explain_guess(
        guess="trace", candidates_before=["crane", "trace"],
        candidates_after=["crane"], is_candidate=True,
    ))
