"""
feedback.py
-----------
Part 2 of the solver: given a guess and the real answer, work out exactly
what colours Wordle would show.

This is used two ways:
  1. During automated benchmarking, so the solver can play a full game
     against itself with no human involved -- we need to know what the
     "real" Wordle would have said.
  2. As the reference definition of the rules that Part 3 (filtering) has
     to respect. If there's ever a disagreement between this file and the
     filtering logic, this file is right, because it mirrors what the
     actual game does.

GREEN  = the letter is in this exact position.
YELLOW = the letter is in the word, but not this position.
GREY   = the letter isn't in the word (beyond what's already accounted
         for -- see the duplicate-letter note below).

THE DUPLICATE-LETTER TRAP
--------------------------
This is the part that's easy to get wrong. Say the answer is SPELL and
you guess SPEED:

    S P E E D
    S P E L L

  - Position 1, 2: S, P match exactly -> green, green.
  - Position 3: E matches SPELL's E -> green.
  - Position 4: your second E -- but SPELL only has one E, and it's
    already been "claimed" by position 3. So this E is grey, not yellow.
    Wordle doesn't tell you "there's an E somewhere else" when you've
    already found every E there is.
  - Position 5: D isn't in SPELL at all -> grey.

The fix is to do this in two passes:
  PASS 1 (greens): walk through position by position. Wherever the guess
  matches the answer exactly, mark it green and "use up" one copy of
  that letter from the answer's remaining pool.
  PASS 2 (yellows/greys): for every position that wasn't already green,
  check whether the answer still has an unclaimed copy of that letter
  left in its pool. If yes, yellow, and claim it. If no, grey.

Doing greens first and yellows second is what makes this correct --
if you tried to do it in one left-to-right pass, an early yellow could
wrongly "steal" a letter that a later green needed.
"""

from collections import Counter

GREEN = "G"
YELLOW = "Y"
GREY = "X"


def get_feedback(guess: str, answer: str) -> str:
    """
    Return the 5-character feedback string (e.g. "GYXXG") Wordle would
    show for this guess against this answer.

    Both words are assumed to already be lowercase, 5-letter words --
    validating that is the caller's job, not this function's, so this
    stays a small, single-purpose piece of logic.
    """
    guess = guess.lower()
    answer = answer.lower()
    result = [GREY] * 5

    # Pass 1: lock in the greens, and keep a running count of what's left
    # in the answer once those greens are accounted for.
    remaining = Counter(answer)
    for i in range(5):
        if guess[i] == answer[i]:
            result[i] = GREEN
            remaining[guess[i]] -= 1

    # Pass 2: for everything that isn't already green, see if the answer
    # still has an unclaimed copy of that letter.
    for i in range(5):
        if result[i] == GREEN:
            continue
        letter = guess[i]
        if remaining[letter] > 0:
            result[i] = YELLOW
            remaining[letter] -= 1
        # else: stays GREY -- either the letter isn't in the answer at
        # all, or every copy of it has already been claimed by a green
        # or an earlier yellow.

    return "".join(result)
