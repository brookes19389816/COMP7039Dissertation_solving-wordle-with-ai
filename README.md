# COMP7039Dissertation_solving-wordle-with-ai
MSc AI Dissertation on Solving Wordle with the help of AI

# Wordle Assistant

A hybrid constraint-satisfaction + entropy solver for Wordle, supporting both
Standard and Hard Mode, with a plain-English explanation layer, a CLI, and a
browser-based web app. Built to match the three-layer architecture in the
dissertation's Methodology chapter: the solver decides, the explainer only
narrates.

## Layout

```
wordle_solver/
  wordle_solver/
    data/
      answers.txt        2,315 official Wordle answer words
      all_guesses.txt    12,972 words accepted as guesses (answers included)
    word_list.py          Part 1 -- loading the word lists
    feedback.py            Part 2 -- simulating Wordle's own G/Y/X feedback
    solver.py               Parts 3+4 -- candidate filtering, entropy scoring,
                             Hard Mode enforcement (this is the core module)
    game.py                  self-play used by the benchmark (never used by
                              a real player -- it always knows the answer)
    explainer.py              Layer 2 (template) -- turns a solver decision
                              into a sentence (adapted from wordle_explainer.py)
    llm_explainer.py           Layer 2 (live) -- the actual LLM call, with a
                              guaranteed fallback to the template above if
                              it's unavailable or fails for any reason
    cli.py                    Layer 3 -- the interactive command-line tool
  tests/
    test_solver.py           pytest unit tests, focused on the duplicate-
                              letter edge cases that are easy to get wrong
  webapp/
    wordle_assistant_webapp.html   the browser version -- open it directly,
                                    no installation or server needed
    solver-core.js                  the same solving logic, ported to JS
                                    (tested to match the Python results
                                    exactly -- see test-solver-core.js)
    test-solver-core.js             checks the JavaScript logic matches Python
    test-page-modes.js              plays whole games in the real page
    test-page-explanations.js       checks the explanation panel and fallback
    test-page-llm-cache.js          checks a repeated situation reuses one AI reply
    package.json                    lets npm test run all four of the above
    answers.json, all_guesses.json  the word lists the JavaScript tests use
  benchmark.py               runs the solver against every real answer word
  results_standard.csv       raw results from the Standard Mode benchmark
  results_hard.csv           raw results from the Hard Mode benchmark
```

## Getting it running on your own computer

### 1. Check you have Python

Open a terminal (Mac: Terminal app; Windows: Command Prompt or PowerShell)
and run:

```bash
python3 --version
```

(On Windows, try `python --version` if `python3` isn't recognised.) You need
3.9 or newer. If this fails entirely, install Python from
[python.org/downloads](https://python.org/downloads) first -- on Windows,
tick "Add Python to PATH" during install, or the commands below won't find it.

### 2. Unzip the package and open a terminal there

Unzip `wordle_solver.zip` wherever you like, then `cd` into it:

```bash
cd path/to/wordle_solver
```

### 3. (Recommended) Create a virtual environment

This keeps the packages below separate from anything else on your system.

```bash
python3 -m venv venv

# Activate it -- Mac/Linux:
source venv/bin/activate
# Activate it -- Windows (Command Prompt):
venv\Scripts\activate.bat
# Activate it -- Windows (PowerShell):
venv\Scripts\Activate.ps1
```

You'll know it worked because your prompt now starts with `(venv)`. You'll
need to run the activate command again each time you open a new terminal to
work on this.

### 4. Install the dependencies

```bash
pip install numpy pytest openai
```

### 5. Confirm it actually works

```bash
python -m pytest tests/ -v
```

You should see 34 tests, all passing. If this works, everything below will
too.

### 6. Play it

```bash
python -m wordle_solver.cli
```

It'll ask if you're playing Hard Mode, then suggest a word each turn --
play that word in the real Wordle, and type back the colours it shows you
(G for green, Y for yellow, X for grey -- e.g. `GYXXG`).

### 7. (Optional) Turn on live AI-written explanations

Without this, explanations use the rule-based template -- which is the
designed fallback, not a lesser mode. To use a real LLM call instead, get
an API key from [platform.openai.com](https://platform.openai.com) and:

```bash
# Mac/Linux:
export OPENAI_API_KEY="paste-your-key-here"
# Windows (Command Prompt):
set OPENAI_API_KEY=paste-your-key-here
# Windows (PowerShell):
$env:OPENAI_API_KEY="paste-your-key-here"
```

Then run the CLI again as in step 6 -- the banner at the top will confirm
which mode it's using.

### 8. Try the web version

No installation needed at all -- go to `webapp/` and double-click
`wordle_assistant_webapp.html`, or drag it into any browser window. It runs
entirely on your machine; nothing is sent anywhere.

### 9. (Optional) Re-run the full benchmark yourself

Only do this if you want to reproduce the reported numbers from scratch --
it isn't needed to use the tool.

```bash
python benchmark.py --mode hard --start 0 --end 2315        # ~15 seconds
python benchmark.py --mode standard --start 0 --end 2315    # ~13 minutes
python benchmark.py --mode hard --summarise
python benchmark.py --mode standard --summarise
```

Standard Mode is much slower because it scores the full ~13,000-word
dictionary rather than just the remaining candidates -- see `solver.py`'s
docstring for why that trade-off exists.

### 10. (Optional) Run the browser tests

These check the web app itself by playing whole games in the real page,
the way a person would: clicking tiles and buttons, then reading what the
page shows. They need Node.js (the LTS version from nodejs.org). Then,
from the project folder:

```bash
cd webapp
npm install    # once only: downloads jsdom, a small stand in for a browser
npm test
```

You should see "16 passed, 0 failed" for the logic tests, then a line
starting with PASS for each check in the real page. If anything is wrong,
the run stops at a line starting with FAIL that says what broke.

### If something goes wrong

- **`python3: command not found`** -- try `python` instead of `python3`
  (common on Windows).
- **`pip: command not found`** -- try `pip3`, or `python3 -m pip install ...`.
- **`ModuleNotFoundError: No module named 'wordle_solver'`** -- make sure
  you're running commands from inside the unzipped folder (the one
  containing `benchmark.py` and the `wordle_solver/` subfolder), not from
  inside `wordle_solver/wordle_solver/`.
- **Permission errors installing packages** -- almost always means the
  virtual environment from step 3 isn't active; check your prompt starts
  with `(venv)` and try again.

## Benchmark results (all 2,315 official answers, not a smaller stand-in list)

| Mode     | Win rate       | Avg. guesses (won games) | Avg. guesses (losses counted as 6) |
|----------|----------------|---------------------------|--------------------------------------|
| Standard | 2307/2315 (99.65%) | 3.517 | 3.525 |
| Hard     | 2303/2315 (99.48%) | 3.581 | 3.594 |

For comparison, Bertsimas & Paskov's exact dynamic-programming solver --
which guarantees a win every time and requires days of computation on
a 64-core machine -- achieves 3.421 (Standard) and 3.508 (Hard Mode). This
solver is a one-step greedy heuristic with no multi-turn lookahead, so
landing within roughly a tenth of a guess of the proven mathematical
optimum, in well under a second per game, is the expected trade-off.

Standard Mode beating Hard Mode on both win rate and average guesses is
exactly what theory predicts: every Hard-Mode-legal guess sequence is also
legal in Standard Mode, so Standard Mode can only do as well or better.

## Design decisions worth knowing about

- **Both modes score only among remaining candidates once few are left**
  (see `solver.select_guess_pool`). Below ~20 candidates, Greenberg (2024,
  cited in the literature review) found that restricting to candidates
  costs almost nothing against the full entropy-optimal approach, and it's
  what makes Hard Mode compliance fall out of the design for free.
- **Standard Mode uses the full ~13,000-word dictionary above that
  threshold**, since that's where a "probe" word -- one that can't be the
  answer but splits the field well -- can actually help. This is the real,
  measured difference between the two modes, not just a label.
- **The opening guess is computed once and cached**, not per game --
  every game starts from an identical position, so recomputing it per
  simulated game would just repeat the same expensive calculation
  thousands of times for no benefit.
- **The web app is a separate port of the same logic**, in JavaScript,
  because a Python program can't run inside a browser page. It's tested
  against the same known-correct results as the Python version (see
  `webapp/test-solver-core.js`) so the two agree, not just each being
  internally consistent.
