"""
benchmark.py
------------
Runs the solver against every real Wordle answer -- not a smaller
stand-in list -- once in Standard Mode and once in Hard Mode, and
reports the honest win rate and average guesses for each.

Usage:
    python benchmark.py --mode hard --start 0 --end 2315
    python benchmark.py --mode standard --start 0 --end 500

Results are appended to a CSV (results_<mode>.csv) rather than held only
in memory, so a long run can be done in several smaller chunks -- handy
because Standard Mode's full-dictionary scoring makes each game roughly
25x slower than Hard Mode's. Run it in a few pieces covering the whole
answer list, then call --summarise to combine them into the final
numbers.
"""

import argparse
import csv
import os
import time

from wordle_solver import game
from wordle_solver import word_list as wl


def run_chunk(mode: str, start: int, end: int) -> None:
    hard_mode = mode == "hard"
    answers = wl.load_answers()
    all_guesses = wl.load_all_guesses()
    chunk = answers[start:end]

    out_path = f"results_{mode}.csv"
    write_header = not os.path.exists(out_path)

    t0 = time.time()
    with open(out_path, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["answer", "num_guesses", "won", "guesses"])
        for i, answer in enumerate(chunk):
            result = game.simulate_game(answer, answers, all_guesses, hard_mode=hard_mode)
            writer.writerow(
                [result.answer, result.num_guesses, result.won, " ".join(result.guesses)]
            )
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                print(
                    f"  [{mode}] {start + i + 1}/{end} done "
                    f"({elapsed:.1f}s elapsed, {elapsed / (i + 1):.2f}s/game)"
                )
    print(f"Wrote {len(chunk)} results for [{start}:{end}) to {out_path} "
          f"in {time.time() - t0:.1f}s")


def summarise(mode: str) -> None:
    out_path = f"results_{mode}.csv"
    with open(out_path, newline="") as f:
        rows = list(csv.DictReader(f))

    n = len(rows)
    wins = sum(1 for r in rows if r["won"] == "True")
    avg_guesses = sum(int(r["num_guesses"]) for r in rows) / n
    avg_guesses_won_only = sum(
        int(r["num_guesses"]) for r in rows if r["won"] == "True"
    ) / max(wins, 1)
    losses = [r["answer"] for r in rows if r["won"] != "True"]

    print(f"\n=== {mode.upper()} MODE -- {n} words ===")
    print(f"Win rate:            {wins}/{n} ({100 * wins / n:.2f}%)")
    print(f"Average guesses:     {avg_guesses:.3f} (counting losses as 6)")
    print(f"Average guesses:     {avg_guesses_won_only:.3f} (won games only)")
    if losses:
        print(f"Words not solved in 6: {losses}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["standard", "hard"], required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=2315)
    parser.add_argument("--summarise", action="store_true",
                         help="Skip running games; just summarise results_<mode>.csv so far.")
    args = parser.parse_args()

    if args.summarise:
        summarise(args.mode)
    else:
        run_chunk(args.mode, args.start, args.end)
