"""
game.py
-------
Plays one full game of Wordle against a *known* answer, with no human
involved. This is what lets the benchmark find out how the solver would
have done against every real Wordle answer, automatically.

It's kept separate from cli.py because it's solving a different problem:
this file always knows the answer (it's testing the solver), whereas
cli.py never does (it's helping a real player). Mixing the two would
mean the interactive tool had a "cheat mode" lying around inside it,
which is exactly the kind of thing that's easy to trust by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import feedback as fb
from . import solver as sv

MAX_GUESSES = 6


@dataclass
class GameResult:
    answer: str
    guesses: List[str] = field(default_factory=list)
    won: bool = False

    @property
    def num_guesses(self) -> int:
        return len(self.guesses)


def simulate_game(
    answer: str, all_answers: List[str], all_guesses: List[str], hard_mode: bool
) -> GameResult:
    """
    Play out one game against `answer`, choosing every guess the same
    way the assistant would for a real player, and return what happened.

    `all_answers` and `all_guesses` are passed in (rather than reloaded
    here) so the benchmark can load the word lists once and reuse them
    across all 2,315 games -- reloading text files thousands of times
    would be a waste of the very speed we vectorised solver.py to get.

    THIS is where Standard Mode and Hard Mode actually diverge:
      - Hard Mode always scores candidates as its own guess pool, so
        every guess it ever makes already satisfies every constraint
        revealed so far -- which is the rule Hard Mode enforces.
      - Standard Mode is free to score the full dictionary instead,
        so it can occasionally spend a guess on a word that can't be
        the answer, purely because it splits the remaining candidates
        more evenly than any real candidate would. It only bothers
        with that when there are enough candidates left for it to be
        worth the extra computation (see solver.select_guess_pool).
    """
    result = GameResult(answer=answer)
    candidates = list(all_answers)

    opener, _ = sv.opening_guess(tuple(all_answers))
    guess = opener

    for _ in range(MAX_GUESSES):
        result.guesses.append(guess)
        observed = fb.get_feedback(guess, answer)

        if observed == fb.GREEN * 5:
            result.won = True
            break

        candidates = sv.filter_candidates(candidates, guess, observed)

        if not candidates:
            # Every candidate got filtered out -- shouldn't happen with
            # a correct filter against a real answer, but fail loudly
            # rather than silently guessing nonsense if it ever does.
            raise RuntimeError(
                f"No candidates left solving for '{answer}' after "
                f"guessing {result.guesses} -- this points to a bug in "
                f"filter_candidates, not bad luck."
            )

        guess_pool = sv.select_guess_pool(candidates, all_guesses, hard_mode)
        guess, _ = sv.best_guess(candidates, guess_pool)

    return result
