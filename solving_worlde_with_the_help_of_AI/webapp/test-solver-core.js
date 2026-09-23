// Checks that the JavaScript version of the solver behaves exactly like
// the Python original, using the real word lists and known answers.
const assert = require('assert');
const fs = require('fs');
const sv = require('./solver-core.js');

const answers = JSON.parse(fs.readFileSync(__dirname + '/answers.json'));
const allGuesses = JSON.parse(fs.readFileSync(__dirname + '/all_guesses.json'));

let passed = 0, failed = 0;
function test(name, fn) {
  try {
    fn();
    console.log('PASS:', name);
    passed++;
  } catch (e) {
    console.log('FAIL:', name, '--', e.message);
    failed++;
  }
}

test('word lists load with the real, official counts', () => {
  assert.strictEqual(answers.length, 2315);
  assert.strictEqual(allGuesses.length, 12972);
});

test('all green on exact match', () => {
  assert.strictEqual(sv.feedbackToString(sv.getFeedback('crane', 'crane')), 'GGGGG');
});

test('all grey on no shared letters', () => {
  assert.strictEqual(sv.feedbackToString(sv.getFeedback('frown', 'quiet')), 'XXXXX');
});

test('duplicate-letter case: SPEED vs SPELL matches the Python result exactly (GGGXX)', () => {
  assert.strictEqual(sv.feedbackToString(sv.getFeedback('speed', 'spell')), 'GGGXX');
});

test('entropy is zero with one candidate left', () => {
  assert.strictEqual(sv.entropyBits(['crane'], 'crane'), 0);
});

test('entropy prefers a guess that actually splits the field', () => {
  const candidates = ['crane', 'trace', 'stare', 'board'];
  const useless = sv.entropyBits(candidates, 'whizz'); // shares no letters with any of them
  const useful = sv.entropyBits(candidates, 'crane');
  assert.strictEqual(useless, 0);
  assert.ok(useful > useless);
});

test('filterCandidates matches manual simulation, same as the Python test', () => {
  const candidates = answers.slice(0, 200);
  const guess = 'audio';
  const observedPattern = sv.patternToInt(sv.getFeedback(guess, 'radio'));
  const filtered = sv.filterCandidates(candidates, guess, observedPattern);
  const expected = candidates.filter(c => sv.patternToInt(sv.getFeedback(guess, c)) === observedPattern);
  assert.deepStrictEqual(filtered.sort(), expected.sort());
});

test('opening guess "raise" scores the same entropy as the Python run (5.878 bits)', () => {
  // This is the actual opener the Python package computed and cached
  // (solver.opening_guess) -- cross-checking the JS port reproduces the
  // same number is the strongest evidence the two implementations agree,
  // not just on toy cases but on the real 2,315-word answer list.
  const entropy = sv.entropyBits(answers, 'raise');
  assert.ok(Math.abs(entropy - 5.878) < 0.005, `got ${entropy}`);
});

test('hard mode validation rejects a guess missing a confirmed green', () => {
  const complaint = sv.validateHardModeGuess('trace', { 0: 'c' }, {});
  assert.ok(complaint && complaint.includes('position 1'));
});

test('hard mode validation accepts a guess honouring all constraints', () => {
  const complaint = sv.validateHardModeGuess('crate', { 0: 'c' }, {});
  assert.strictEqual(complaint, null);
});

test('bestGuess over a real ~150-candidate slice matches expected shape', () => {
  const candidates = answers.slice(500, 650); // 150 candidates
  const { word, entropy } = sv.bestGuess(candidates, candidates);
  assert.ok(candidates.includes(word));
  assert.ok(entropy > 0);
});

test('topGuesses top pick matches bestGuess exactly', () => {
  const candidates = answers.slice(300, 450);
  const best = sv.bestGuess(candidates, candidates);
  const top = sv.topGuesses(candidates, candidates, 3);
  assert.strictEqual(top[0].word, best.word);
  assert.ok(Math.abs(top[0].entropy - best.entropy) < 1e-6);
});

test('topGuesses is sorted highest entropy first', () => {
  const candidates = answers.slice(0, 120);
  const top = sv.topGuesses(candidates, candidates, 5);
  const entropies = top.map(t => t.entropy);
  const sorted = [...entropies].sort((a, b) => b - a);
  assert.deepStrictEqual(entropies, sorted);
});

test('patternCount is within the valid 1..243 range', () => {
  const candidates = answers.slice(0, 200);
  const count = sv.patternCount(candidates, 'raise');
  assert.ok(count >= 1 && count <= 243);
});

test('patternCount is exactly 132 for the real opener, matching Python', () => {
  const count = sv.patternCount(answers, 'raise');
  assert.strictEqual(count, 132);
});

test('patternCount is 1 with a single candidate', () => {
  assert.strictEqual(sv.patternCount(['crane'], 'crane'), 1);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
