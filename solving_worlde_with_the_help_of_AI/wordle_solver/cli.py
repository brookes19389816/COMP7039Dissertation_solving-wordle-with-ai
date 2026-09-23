"""
cli.py
------
Layer 3 of the architecture: the interface a real player actually talks
to. Run this alongside the real Wordle in a browser tab -- play the
suggested word there, read off the colours it gives you, type them back
in here as a 5-letter string of G (green), Y (yellow) and X (grey), and
the assistant works out what to try next.

This file never knows the answer -- unlike game.py, which is only used
for self-play benchmarking against words we already know. Keeping that
boundary means a genuine player never has to wonder whether the
"cheating" self-play code could somehow leak into their game.

A note on ordering: the guess is shown first, feedback is asked for
second, and the *explanation* of why that guess was chosen comes third,
after filtering. That might seem backwards -- surely you'd want the
"why" before typing the word in? -- but explain_guess's whole design is
to describe what a guess actually achieved ("narrowed N down to M"), and
that number only exists once the feedback is in. Showing it as a
recap -- "here's why that was a good move" -- is both the only way the
sentence is factually true, and, for a tool meant to teach strategy
rather than just dispense answers, arguably the more useful moment for
it to land anyway.
"""

from __future__ import annotations

import os

from . import feedback as fb
from . import llm_explainer
from . import solver as sv
from . import word_list as wl

VALID_FEEDBACK_CHARS = {fb.GREEN, fb.YELLOW, fb.GREY}


def _ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer y or n.")


def _ask_feedback(guess: str) -> str:
    while True:
        raw = input(
            f'Feedback for "{guess.upper()}" (5 letters, G/Y/X): '
        ).strip().upper()
        if len(raw) == 5 and all(c in VALID_FEEDBACK_CHARS for c in raw):
            return raw
        print(
            "That doesn't look like 5 characters of G, Y and X "
            "(e.g. GYXXG). Try again."
        )


def _constraints_from_history(guesses_and_feedback):
    """Turn the guesses made so far into the greens/required_letters
    dicts validate_hard_mode_guess needs."""
    greens: dict = {}
    required_letters: dict = {}
    for guess, observed in guesses_and_feedback:
        for i, ch in enumerate(observed):
            if ch == fb.GREEN:
                greens[i] = guess[i]
        letter_counts: dict = {}
        for i, ch in enumerate(observed):
            if ch in (fb.GREEN, fb.YELLOW):
                letter_counts[guess[i]] = letter_counts.get(guess[i], 0) + 1
        for letter, count in letter_counts.items():
            required_letters[letter] = max(required_letters.get(letter, 0), count)
    return greens, required_letters


def run() -> None:
    print("=" * 60)
    print("Wordle Assistant -- plays alongside your real game")
    print("=" * 60)
    if os.environ.get("OPENAI_API_KEY"):
        print("(Explanations: live LLM call, with template fallback if it fails)")
    else:
        print("(Explanations: template only -- set OPENAI_API_KEY to enable the LLM)")
    hard_mode = _ask_yes_no("Are you playing Hard Mode?")
    print()

    answers = wl.load_answers()
    all_guesses = wl.load_all_guesses()
    candidates = list(answers)
    history: list = []

    for turn in range(1, 7):
        candidates_before = candidates

        if len(candidates_before) == 1:
            guess, entropy, is_candidate = candidates_before[0], 0.0, True
        else:
            if turn == 1:
                pool = answers
            else:
                pool = sv.select_guess_pool(candidates_before, all_guesses, hard_mode)
            guess, entropy, is_candidate = sv.top_guesses(candidates_before, pool, n=1)[0]

        print(f"\nTurn {turn} -- try: {guess.upper()}")
        observed = _ask_feedback(guess)

        if observed == fb.GREEN * 5:
            print(f"\nSolved it in {turn} guess{'es' if turn > 1 else ''}. Nice.")
            return

        history.append((guess, observed))
        candidates = sv.filter_candidates(candidates_before, guess, observed)

        if not candidates:
            print(
                "\nNo remaining word fits that feedback -- double-check "
                "what you typed (a mistyped G/Y/X is the usual culprit)."
            )
            return

        print(
            llm_explainer.explain_guess_with_llm(
                guess=guess,
                candidates_before=candidates_before,
                candidates_after=candidates,
                entropy_bits=entropy,
                hard_mode=hard_mode,
                is_candidate=is_candidate,
            )
        )

        if hard_mode:
            greens, required_letters = _constraints_from_history(history)
            override = input(
                "Press Enter to use the assistant's next suggestion, or "
                "type your own guess to check it's legal: "
            ).strip().lower()
            if override:
                complaint = sv.validate_hard_mode_guess(override, greens, required_letters)
                if complaint:
                    print(f"That guess isn't legal in Hard Mode: {complaint}")
                else:
                    print("That guess is legal -- go ahead and play it yourself.")

    print(f"\nOut of guesses. The word may have been one of: {candidates}")


if __name__ == "__main__":
    run()
