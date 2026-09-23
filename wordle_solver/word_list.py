"""
word_list.py
------------
Part 1 of the solver: getting hold of the words it's allowed to work with.

Wordle actually has two lists, and the difference matters:

  - ANSWERS   -- the ~2,315 words the secret word is actually drawn from.
                 These are the everyday, recognisable words.
  - ALL_GUESSES -- every word (~12,972) the game will accept as a guess,
                 including a lot of obscure ones that were never going to
                 be the answer but are still "real words" for spelling
                 purposes.

Why keep them separate instead of just using one big list? Because the
solver's strategy depends on the distinction:
  - The secret word can ONLY come from ANSWERS, so once we're picking our
    final guess (or reasoning about "what could the answer be"), ANSWERS
    is the list that matters.
  - Early guesses can sometimes usefully be a word that we know ISN'T
    the answer, just because it tests good letters. That's what
    ALL_GUESSES is for.

If the real word-list files aren't there for some reason, we fall back to
a small built-in list so the solver can still limp along and be tested --
better than crashing outright.
"""

from pathlib import Path
from typing import List

DATA_DIR = Path(__file__).parent / "data"

# A small get-us-out-of-trouble list, only used if the real files are
# missing. Real Wordle answers, just not all 2,315 of them.
_FALLBACK_WORDS = [
    "slate", "crane", "trace", "stare", "adieu", "raise", "arise", "irate",
    "roate", "tears", "arose", "later", "stone", "spine", "shale", "crate",
    "heart", "world", "house", "mount", "plant", "sword", "brick", "chair",
]


def _read_word_file(path: Path) -> List[str]:
    """
    Read one word per line from a text file, cleaning up as we go.

    We lowercase everything and strip whitespace so the file doesn't have
    to be perfectly formatted. Anything that isn't exactly 5 alphabetic
    characters gets skipped rather than crashing the whole load -- a
    stray blank line or a typo in the word list shouldn't take the
    solver down with it.
    """
    words = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if len(word) == 5 and word.isalpha():
                words.append(word)
    return words


def load_answers() -> List[str]:
    """
    Load the list of words the secret answer can actually be drawn from.

    Falls back to a small built-in list (and prints a warning) if the
    real data file isn't present, so the solver still runs -- just with
    a smaller, less faithful word pool.
    """
    path = DATA_DIR / "answers.txt"
    if path.exists():
        return _read_word_file(path)
    print(
        f"[word_list] Couldn't find {path}, falling back to a built-in "
        f"list of {len(_FALLBACK_WORDS)} words. Results won't match the "
        f"real game closely."
    )
    return list(_FALLBACK_WORDS)


def load_all_guesses() -> List[str]:
    """
    Load every word the game will accept as a guess (answers included).

    This is the bigger list. If it's missing, we fall back to just the
    answers list -- a smaller guess pool than the real game allows, but
    still internally consistent (every answer is always a legal guess).
    """
    path = DATA_DIR / "all_guesses.txt"
    if path.exists():
        return _read_word_file(path)
    print(
        f"[word_list] Couldn't find {path}, falling back to the answers "
        f"list as the guess pool too."
    )
    return load_answers()
