"""
llm_explainer.py
-----------------
The last piece of Layer 2: an actual call to an LLM to phrase the
explanation, rather than the fixed template in explainer.py.

This is intentionally a thin wrapper around explainer.explain_guess,
not a replacement for it. The template already decides WHAT gets said
-- this file adds asking an LLM to say the same thing more naturally.
If anything goes wrong -- no API key set, no internet, the API is
down, a malformed response -- this quietly falls back to the template
rather than crashing or leaving the player with nothing.

Needs an OpenAI API key in the OPENAI_API_KEY environment variable.
Nothing in this repository contains a key -- there isn't one to ship,
and there shouldn't be: an API key is a secret that belongs to whoever
is running the assistant, not something baked into shared code.
"""

from __future__ import annotations

import os
from typing import Iterable, List, Optional

from . import explainer

MODEL = "gpt-4o"

# Explanations already fetched in this session, keyed by the exact prompt
# sent. The same situation comes up often when a game is replayed during
# testing or a demo, and asking the API again for an answer we already
# have would only cost time, money and energy for nothing.
_explanation_cache: dict = {}

_SYSTEM_PROMPT = (
    "You explain a Wordle guess to a casual player in ONE short, "
    "friendly sentence, occasionally two. You are NOT choosing the "
    "guess -- it has already been chosen by a separate solver. Say "
    "whether the word could itself be the answer, or is just a smart "
    "way to narrow things down, in plain everyday language. Do not "
    "mention bits, entropy, probabilities, or any other technical "
    "term, and do not cite exact numbers beyond how many words are "
    "still possible. A reader with zero technical background should "
    "understand it instantly. Do not invent facts or suggest a "
    "different word."
)


def _build_prompt(
    guess: str,
    n_before: int,
    n_after: Optional[int],
    hard_mode: bool = False,
    is_candidate: Optional[bool] = None,
) -> str:
    """
    Build the user-facing prompt from the solver's real output. Kept
    deliberately sparse: this used to also pass entropy, an outcome
    count, and a named runner-up guess, but that level of detail is
    for this project's own report, not for a player mid-game (see the
    revision note at the top of explainer.py).
    """
    lines = [
        f'The solver chose the guess "{guess.upper()}".',
        f"Before this guess, {n_before} words were still possible.",
    ]
    if n_after is not None:
        lines.append(f"After this guess's feedback, {n_after} words remain possible.")
    if is_candidate is not None:
        lines.append(
            "This word could itself have been the correct answer."
            if is_candidate else
            "This word could NOT itself have been the correct answer; it only narrows things down."
        )
    lines.append(f"Hard Mode is {'ON' if hard_mode else 'off'}.")
    lines.append("Explain this in one short, friendly sentence for a casual player.")
    return "\n".join(lines)


def explain_guess_with_llm(
    guess: str,
    candidates_before: Iterable,
    candidates_after: Iterable,
    entropy_bits: float = 0.0,
    hard_mode: bool = False,
    is_candidate: Optional[bool] = None,
    hard_mode_constraints: Optional[List[str]] = None,
) -> str:
    """
    Same job as explainer.explain_guess, but tries an LLM call first
    and only falls back to the template if that call can't be
    completed for any reason. `entropy_bits` is accepted for backward
    compatibility with existing callers but no longer surfaced to the
    player, in either the template or the live call.
    """
    candidates_before = list(candidates_before)
    candidates_after = list(candidates_after)

    fallback = explainer.explain_guess(
        guess=guess,
        candidates_before=candidates_before,
        candidates_after=candidates_after,
        is_candidate=is_candidate,
        hard_mode_constraints=hard_mode_constraints,
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return fallback

    try:
        import openai  # imported here, not at module level, so the rest of
        # the package still works even if openai isn't installed --
        # only this one function needs it.

        client = openai.OpenAI(api_key=api_key)
        prompt = _build_prompt(
            guess=guess,
            n_before=len(candidates_before),
            n_after=len(candidates_after),
            hard_mode=hard_mode,
            is_candidate=is_candidate,
        )
        if prompt in _explanation_cache:
            return _explanation_cache[prompt]
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=100,
            timeout=8,
        )
        text = response.choices[0].message.content
        if text and text.strip():
            _explanation_cache[prompt] = text.strip()
            return text.strip()
        return fallback

    except Exception:
        # Deliberately broad: an invalid key, a timeout, a rate limit,
        # a network blip -- none of these are the player's problem.
        return fallback
