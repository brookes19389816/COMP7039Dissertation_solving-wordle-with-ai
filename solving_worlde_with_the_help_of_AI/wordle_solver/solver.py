"""
solver.py
---------
The heart of the assistant: Parts 3 and 4 from the dissertation's
Implementation chapter.

  Part 3 -- filter the candidate list down using whatever feedback we've
            been given so far.
  Part 4 -- of what's left, work out which guess teaches us the most,
            using Shannon entropy.

WHY NUMPY, WHEN feedback.py IS PLAIN PYTHON?
---------------------------------------------
feedback.py is the *readable* definition of the rules -- it's short
enough to read top to bottom and trust. But entropy scoring needs to run
that same logic thousands of times per guess (once per candidate answer,
for every word we're considering guessing), and doing that with a plain
Python loop is too slow to benchmark the whole game across all 2,315
real answers.

So this file re-implements the *same* two-pass green-then-yellow logic
from feedback.py, but on whole arrays of words at once with numpy. It is
not a different algorithm -- it's the fast version of the same one, and
the tests in tests/test_solver.py check the two agree.

WHY THE GUESS POOL IS "REMAINING CANDIDATES", NOT THE FULL DICTIONARY
------------------------------------------------------------------------
After the first guess, this solver only considers words that are still
possible answers when picking the next guess -- it doesn't reach for an
obscure word purely to "probe" for information. Greenberg (2024, cited
in the literature review) found that restricting guesses this way costs
only a small fraction of a guess on average against the full
entropy-optimal approach, while being simpler to reason about and much
faster to run. It also means Hard Mode's rule -- you may only guess
words consistent with what you already know -- falls out of the design
for free, exactly as described in the Methodology chapter: the same
filtered candidate list is both "what might be the answer" and "what
you're allowed to guess next".

The one exception is the very first guess of the game, where there are
no candidates to restrict to yet. That's computed once (not once per
simulated game -- every game starts the same way, since no information
exists yet) and reused.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import feedback as fb

NUM_PATTERNS = 3 ** 5  # 243 -- every letter is grey(0), yellow(1) or green(2)


def _words_to_codes(words: Sequence[str]) -> np.ndarray:
    """Turn a list of 5-letter words into an (N, 5) array of 0-25 ints."""
    arr = np.frombuffer("".join(words).encode("ascii"), dtype=np.uint8)
    arr = arr.reshape(len(words), 5) - ord("a")
    return arr


def _pattern_batch(guess_codes: np.ndarray, answer_matrix: np.ndarray) -> np.ndarray:
    """
    The fast, vectorised twin of feedback.get_feedback: given one guess
    (as a length-5 code array) and many candidate answers (an (N, 5)
    code array), return the resulting pattern for each answer as a
    single integer 0-242.

    A pattern is just the 5 digits (grey=0/yellow=1/green=2) read as a
    base-3 number, position 0 being the least significant digit. Which
    digit means what doesn't matter for correctness -- all that matters
    is that equal feedback always produces equal integers, which it does
    here since the mapping is fixed.

    This mirrors feedback.py's two-pass approach exactly:
      pass 1 marks greens and removes them from each answer's letter pool
      pass 2 marks yellows from whatever's left in that pool, else grey
    """
    n = answer_matrix.shape[0]
    result = np.zeros(n, dtype=np.int16)

    # "pool" tracks, per answer word, how many of each letter (a-z) are
    # still unclaimed once greens are accounted for.
    pool = np.zeros((n, 26), dtype=np.int8)
    for letter in range(26):
        pool[:, letter] = np.sum(answer_matrix == letter, axis=1)

    is_green = answer_matrix == guess_codes[np.newaxis, :]
    for pos in range(5):
        letter = guess_codes[pos]
        green_here = is_green[:, pos]
        result += np.where(green_here, 2, 0) * (3 ** pos)
        # A green claims one copy of its letter from that word's pool.
        pool[green_here, letter] -= 1

    for pos in range(5):
        letter = guess_codes[pos]
        not_green_here = ~is_green[:, pos]
        has_spare = pool[:, letter] > 0
        is_yellow = not_green_here & has_spare
        result += np.where(is_yellow, 1, 0) * (3 ** pos)
        # A yellow also claims a copy, so a second occurrence of the
        # same letter later in the guess doesn't double-claim it.
        pool[is_yellow, letter] -= 1

    return result


def filter_candidates(candidates: Sequence[str], guess: str, observed_feedback: str) -> List[str]:
    """
    Part 3: given the feedback Wordle actually returned for `guess`,
    throw out every candidate that couldn't have produced it.

    `observed_feedback` uses feedback.py's G/Y/X string format (e.g.
    "GYXXG") so this function reads naturally next to wherever the
    feedback came from -- a real game, or feedback.get_feedback during
    benchmarking.
    """
    if not candidates:
        return []
    target = _string_to_pattern(observed_feedback)
    guess_codes = _words_to_codes([guess])[0]
    answer_matrix = _words_to_codes(candidates)
    patterns = _pattern_batch(guess_codes, answer_matrix)
    return [w for w, p in zip(candidates, patterns) if p == target]


def _string_to_pattern(feedback_str: str) -> int:
    """Convert a "GYXXG"-style string into the same integer encoding
    _pattern_batch uses, so the two can be compared directly."""
    digit_of = {fb.GREY: 0, fb.YELLOW: 1, fb.GREEN: 2}
    total = 0
    for pos, ch in enumerate(feedback_str):
        total += digit_of[ch] * (3 ** pos)
    return total


def entropy_bits(candidates: Sequence[str], guess: str) -> float:
    """
    Part 4: the expected information gain (in bits) of playing `guess`
    against the current candidate list.

    The idea: group the candidates by what feedback pattern they'd each
    produce against this guess. A guess that spreads candidates evenly
    across many different patterns tells us a lot, whichever pattern we
    actually see -- that's high entropy. A guess where almost everything
    falls into one or two patterns barely narrows things down, whatever
    happens -- low entropy.
    """
    guess_codes = _words_to_codes([guess])[0]
    answer_matrix = _words_to_codes(candidates)
    patterns = _pattern_batch(guess_codes, answer_matrix)
    counts = np.bincount(patterns, minlength=NUM_PATTERNS)
    probs = counts[counts > 0] / len(candidates)
    return float(-np.sum(probs * np.log2(probs)))


def _entropy_for_batch(guess_matrix: np.ndarray, answer_matrix: np.ndarray) -> np.ndarray:
    """
    The same idea as entropy_bits, but for many candidate guesses at
    once: returns one entropy value per row of `guess_matrix`.

    Looping over guess words one at a time in Python and calling numpy
    once per word works, but the per-call overhead adds up fast once
    the guess pool is the full ~13,000-word dictionary rather than a
    small candidate list. Folding the guess dimension into the numpy
    arrays too -- so there's one call doing all of them together --
    is what makes scoring the whole dictionary actually practical.

    This still follows the same two-pass green-then-yellow logic as
    feedback.py and _pattern_batch; it's just doing it for a batch of
    guesses against a batch of answers simultaneously instead of one
    guess at a time.
    """
    n_guesses, n_answers = guess_matrix.shape[0], answer_matrix.shape[0]

    # pool[a, letter] = how many of that letter answer `a` has left to
    # claim. Starts the same for every guess in the batch, so it's
    # rebuilt per guess below rather than carried across the batch.
    base_pool = np.zeros((n_answers, 26), dtype=np.int8)
    for letter in range(26):
        base_pool[:, letter] = np.sum(answer_matrix == letter, axis=1)

    patterns = np.zeros((n_guesses, n_answers), dtype=np.int16)

    for pos in range(5):
        # (n_guesses, n_answers) grid of "does this guess's letter at
        # `pos` match this answer's letter at `pos`?"
        is_green = guess_matrix[:, pos][:, None] == answer_matrix[:, pos][None, :]
        patterns += np.where(is_green, 2, 0) * (3 ** pos)

    # Yellows need the per-answer letter pool, decremented by every
    # green claimed so far -- which depends on the specific guess, so
    # this part can't avoid a small loop over positions the way greens
    # (which only compare single letters) can skip straight to a grid.
    pool = np.broadcast_to(base_pool, (n_guesses, n_answers, 26)).copy()
    for pos in range(5):
        is_green = guess_matrix[:, pos][:, None] == answer_matrix[:, pos][None, :]
        for letter in range(26):
            claimed = is_green & (guess_matrix[:, pos] == letter)[:, None]
            pool[:, :, letter] -= claimed.astype(np.int8)

    for pos in range(5):
        is_green = guess_matrix[:, pos][:, None] == answer_matrix[:, pos][None, :]
        letter_at_pos = guess_matrix[:, pos]
        spare = np.take_along_axis(pool, letter_at_pos[:, None, None].repeat(n_answers, axis=1), axis=2)[:, :, 0]
        is_yellow = (~is_green) & (spare > 0)
        patterns += np.where(is_yellow, 1, 0) * (3 ** pos)
        for letter in range(26):
            claimed = is_yellow & (letter_at_pos == letter)[:, None]
            pool[:, :, letter] -= claimed.astype(np.int8)

    # Turn each row's pattern counts into an entropy value.
    entropies = np.zeros(n_guesses, dtype=np.float64)
    for i in range(n_guesses):
        counts = np.bincount(patterns[i], minlength=NUM_PATTERNS)
        probs = counts[counts > 0] / n_answers
        entropies[i] = -np.sum(probs * np.log2(probs))
    return entropies


def best_guess(
    candidates: Sequence[str],
    guess_pool: Sequence[str],
    batch_size: int = 1500,
) -> Tuple[str, float]:
    """
    Of everything in `guess_pool`, return the one with the highest
    entropy against `candidates`, and what that entropy is.

    `guess_pool` can be much bigger than `candidates` -- in Standard
    Mode it's often the full ~13,000-word dictionary, since a word that
    can't be the answer is still allowed as a guess and might split the
    field better than any real candidate can. Hard Mode calls this with
    `guess_pool == candidates`, which is what makes it Hard Mode (see
    game.py).

    Processed in batches of `batch_size` guesses at a time rather than
    all at once, purely to keep memory use predictable when the guess
    pool is large -- the result is identical either way.

    Ties are broken in favour of a guess that's actually still a
    possible answer -- if two words split the field equally well,
    there's no reason not to prefer the one that might just win the
    game outright. After that, whichever came first in `guess_pool`,
    purely so results are reproducible.
    """
    if len(candidates) == 1:
        # Nothing left to learn -- just guess the one word it could be.
        return candidates[0], 0.0

    guess_pool = list(guess_pool)
    answer_matrix = _words_to_codes(list(candidates))
    candidate_set = set(candidates)

    best_word: Optional[str] = None
    best_entropy = -1.0
    best_is_candidate = False

    for start in range(0, len(guess_pool), batch_size):
        chunk = guess_pool[start:start + batch_size]
        chunk_matrix = _words_to_codes(chunk)
        entropies = _entropy_for_batch(chunk_matrix, answer_matrix)

        for word, entropy in zip(chunk, entropies):
            is_candidate = word in candidate_set
            better = (
                entropy > best_entropy + 1e-9
                or (
                    abs(entropy - best_entropy) <= 1e-9
                    and is_candidate
                    and not best_is_candidate
                )
            )
            if better:
                best_word, best_entropy, best_is_candidate = word, float(entropy), is_candidate

    return best_word, best_entropy


def top_guesses(
    candidates: Sequence[str],
    guess_pool: Sequence[str],
    n: int = 3,
    batch_size: int = 1500,
) -> List[Tuple[str, float, bool]]:
    """
    Like best_guess, but returns the top `n` guesses by entropy instead of
    only the winner, each tagged with whether it's an actual remaining
    candidate.

    This exists for the explanation layer, not for solving. Knowing what
    the runner-up guesses were, and by how much they lost, is exactly the
    information that turns "here's what happened" into "here's why this
    guess specifically was chosen over the alternatives" -- the difference
    between reporting an outcome and explaining a decision.
    """
    if len(candidates) == 1:
        return [(candidates[0], 0.0, True)]

    guess_pool = list(guess_pool)
    answer_matrix = _words_to_codes(list(candidates))
    candidate_set = set(candidates)

    scored: List[Tuple[str, float, bool]] = []
    for start in range(0, len(guess_pool), batch_size):
        chunk = guess_pool[start:start + batch_size]
        chunk_matrix = _words_to_codes(chunk)
        entropies = _entropy_for_batch(chunk_matrix, answer_matrix)
        for word, entropy in zip(chunk, entropies):
            scored.append((word, float(entropy), word in candidate_set))

    # Highest entropy first; among ties, an actual candidate sorts first,
    # for the same reason best_guess prefers one on a tie.
    scored.sort(key=lambda t: (-t[1], not t[2]))
    return scored[:n]


def pattern_count(candidates: Sequence[str], guess: str) -> int:
    """
    How many distinct colour outcomes `guess` could actually produce
    against the current candidates -- out of the 243 that exist in
    principle. A concrete number to put next to the more abstract entropy
    score: "this guess could have come back 47 different ways" is easier
    to picture than "5.9 bits" on its own, even though they're describing
    the same underlying spread.
    """
    guess_codes = _words_to_codes([guess])[0]
    answer_matrix = _words_to_codes(list(candidates))
    patterns = _pattern_batch(guess_codes, answer_matrix)
    return len(set(patterns.tolist()))


@lru_cache(maxsize=4)
def opening_guess(answers: Tuple[str, ...]) -> Tuple[str, float]:
    """
    Work out the best opening guess once and remember it -- every game
    starts from the same position (no feedback yet), so recomputing this
    per game would just be repeating the same expensive calculation
    thousands of times for no benefit.

    `answers` is a tuple (not a list) purely so it's hashable and this
    function can be cached with @lru_cache.
    """
    return best_guess(answers, answers)


def select_guess_pool(
    candidates: Sequence[str], all_guesses: Sequence[str], hard_mode: bool
) -> Sequence[str]:
    """
    The one place that decides what a guess is allowed to be drawn
    from, for either mode. Both game.py (self-play benchmarking) and
    cli.py (a real player) call this rather than each encoding the same
    policy separately -- the two would otherwise be free to quietly
    drift apart, and the benchmark's numbers would stop describing what
    a real player actually gets.

    Hard Mode always restricts to candidates -- that's the rule.
    Standard Mode restricts to candidates too once there are few enough
    left that a "probe" word from outside the candidate list is very
    unlikely to help (see Greenberg, cited in the literature review) --
    otherwise it uses the full guess list, so it can spend a guess on a
    word that can't be the answer purely because it splits the field
    better than any real candidate would.
    """
    if hard_mode or len(candidates) <= PROBE_WORTHWHILE_THRESHOLD:
        return candidates
    return all_guesses


# Shared with game.py's threshold of the same name -- see
# select_guess_pool's docstring for why this exists at all.
PROBE_WORTHWHILE_THRESHOLD = 20


def validate_hard_mode_guess(
    guess: str, greens: dict, required_letters: dict
) -> Optional[str]:
    """
    Check whether `guess` honours everything Hard Mode requires so far,
    and return a plain-English complaint if it doesn't (None if it's
    fine).

    `greens` maps position -> letter for every confirmed spot.
    `required_letters` maps letter -> minimum count it must appear with
    (covers both green and yellow discoveries).

    This is what the Methodology chapter calls "the solver validates any
    word the player types in Hard Mode before accepting it" -- it's kept
    separate from filter_candidates because it's answering a different
    question (is this ONE guess legal?) rather than (which OF MANY
    candidates survive?).
    """
    guess = guess.lower()
    for pos, letter in greens.items():
        if guess[pos] != letter:
            return (
                f"Hard Mode requires '{letter.upper()}' in position "
                f"{pos + 1}, but this guess has '{guess[pos].upper()}'."
            )
    for letter, min_count in required_letters.items():
        if guess.count(letter) < min_count:
            return (
                f"Hard Mode requires at least {min_count} '{letter.upper()}' "
                f"in the guess, based on earlier clues."
            )
    return None
