// solver-core.js
// The same logic as the Python package's feedback.py + solver.py, ported
// to JavaScript so it can run entirely in the browser with no server.
// Tested against the Python implementation's known-correct outputs
// before being wired into any UI -- see test-solver-core.js.

const GREEN = 2, YELLOW = 1, GREY = 0;

function wordToCodes(word) {
  const codes = new Uint8Array(5);
  for (let i = 0; i < 5; i++) codes[i] = word.charCodeAt(i) - 97; // 'a' = 0
  return codes;
}

// The same two-pass algorithm as feedback.py: greens first (claiming a
// letter from the answer's pool), then yellows from whatever's left.
// Returns an array of 5 values, each GREEN/YELLOW/GREY.
function getFeedback(guess, answer) {
  const g = wordToCodes(guess), a = wordToCodes(answer);
  const result = new Uint8Array(5).fill(GREY);
  const pool = new Int8Array(26);
  for (let i = 0; i < 5; i++) pool[a[i]]++;

  for (let i = 0; i < 5; i++) {
    if (g[i] === a[i]) {
      result[i] = GREEN;
      pool[g[i]]--;
    }
  }
  for (let i = 0; i < 5; i++) {
    if (result[i] === GREEN) continue;
    if (pool[g[i]] > 0) {
      result[i] = YELLOW;
      pool[g[i]]--;
    }
  }
  return result;
}

function patternToInt(pattern) {
  let total = 0;
  for (let i = 0; i < 5; i++) total += pattern[i] * Math.pow(3, i);
  return total;
}

function feedbackToString(pattern) {
  const chars = { [GREEN]: 'G', [YELLOW]: 'Y', [GREY]: 'X' };
  // Uint8Array.map() coerces callback results back to uint8 numbers --
  // it can't hold strings, so this has to build the string by hand
  // rather than mapping over the typed array directly.
  let out = '';
  for (let i = 0; i < pattern.length; i++) out += chars[pattern[i]];
  return out;
}

// Part 3: keep only candidates consistent with the guess/feedback pair.
function filterCandidates(candidates, guess, observedPattern) {
  return candidates.filter(c => patternToInt(getFeedback(guess, c)) === observedPattern);
}

// Part 4: expected information gain of `guess` against `candidates`.
function entropyBits(candidates, guess) {
  const counts = new Map();
  for (const c of candidates) {
    const p = patternToInt(getFeedback(guess, c));
    counts.set(p, (counts.get(p) || 0) + 1);
  }
  let entropy = 0;
  const n = candidates.length;
  for (const count of counts.values()) {
    const p = count / n;
    entropy -= p * Math.log2(p);
  }
  return entropy;
}

// Same policy as solver.select_guess_pool in the Python package: Hard
// Mode (or few enough candidates left that probing barely helps, per
// Greenberg 2024) restricts guesses to the candidate list itself;
// otherwise Standard Mode may draw from the full dictionary.
const PROBE_WORTHWHILE_THRESHOLD = 20;

function selectGuessPool(candidates, allGuesses, hardMode) {
  if (hardMode || candidates.length <= PROBE_WORTHWHILE_THRESHOLD) return candidates;
  return allGuesses;
}

// Of everything in `guessPool`, the one with the highest entropy
// against `candidates`. Ties favour an actual candidate, same as the
// Python version, since a tied guess that could also just win outright
// is strictly better than one that can't.
function bestGuess(candidates, guessPool) {
  if (candidates.length === 1) return { word: candidates[0], entropy: 0 };
  const candidateSet = new Set(candidates);
  let best = null, bestEntropy = -1, bestIsCandidate = false;
  for (const word of guessPool) {
    const entropy = entropyBits(candidates, word);
    const isCandidate = candidateSet.has(word);
    const better = entropy > bestEntropy + 1e-9 ||
      (Math.abs(entropy - bestEntropy) <= 1e-9 && isCandidate && !bestIsCandidate);
    if (better) { best = word; bestEntropy = entropy; bestIsCandidate = isCandidate; }
  }
  return { word: best, entropy: bestEntropy };
}

// Like bestGuess, but returns the top n by entropy instead of only the
// winner, each tagged with whether it's an actual remaining candidate --
// ported from solver.py's top_guesses. This is what lets the explanation
// layer say what a guess specifically beat, and by how much, rather than
// only reporting the winner.
function topGuesses(candidates, guessPool, n) {
  if (candidates.length === 1) return [{ word: candidates[0], entropy: 0, isCandidate: true }];
  const candidateSet = new Set(candidates);
  const scored = guessPool.map(word => ({
    word,
    entropy: entropyBits(candidates, word),
    isCandidate: candidateSet.has(word),
  }));
  scored.sort((a, b) => (b.entropy - a.entropy) || (a.isCandidate === b.isCandidate ? 0 : (a.isCandidate ? -1 : 1)));
  return scored.slice(0, n);
}

// How many distinct colour outcomes this guess could actually produce
// against the current candidates -- ported from solver.py's
// pattern_count. A concrete number to sit next to the more abstract
// entropy score.
function patternCount(candidates, guess) {
  const seen = new Set();
  for (const c of candidates) seen.add(patternToInt(getFeedback(guess, c)));
  return seen.size;
}

// Hard Mode validation of a player's own typed guess (not the solver's
// own suggestion, which always already satisfies these by construction).
function validateHardModeGuess(guess, greens, requiredLetters) {
  for (const [pos, letter] of Object.entries(greens)) {
    if (guess[pos] !== letter) {
      return `Hard Mode requires '${letter.toUpperCase()}' in position ${Number(pos) + 1}, but this guess has '${guess[pos].toUpperCase()}'.`;
    }
  }
  for (const [letter, minCount] of Object.entries(requiredLetters)) {
    const actual = guess.split('').filter(c => c === letter).length;
    if (actual < minCount) {
      return `Hard Mode requires at least ${minCount} '${letter.toUpperCase()}' in the guess, based on earlier clues.`;
    }
  }
  return null;
}

if (typeof module !== 'undefined') {
  module.exports = {
    GREEN, YELLOW, GREY, getFeedback, patternToInt, feedbackToString,
    filterCandidates, entropyBits, selectGuessPool, bestGuess, topGuesses, patternCount,
    validateHardModeGuess, PROBE_WORTHWHILE_THRESHOLD,
  };
}
