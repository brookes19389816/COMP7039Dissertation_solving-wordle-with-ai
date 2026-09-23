// Plays whole games in the real page, the way a person would: clicking
// tiles and buttons, then reading what the page shows. Covers both modes,
// "Assist me" (you report the colours) and "Watch it solve itself" (the
// page plays on its own against a word you give it).
const path = require('path');
const fs = require('fs');
const { JSDOM } = require('jsdom');

// The page sits in the same folder as this test, wherever that folder is.
const html = fs.readFileSync(path.join(__dirname, 'wordle_assistant_webapp.html'), 'utf8');

// Stops the run with a clear message if something is wrong, so a broken
// page can never be reported as passing.
function check(condition, message) {
  if (!condition) throw new Error(message);
}
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

// Clicks each tile of the current row the right number of times to show
// the colours a real game would give for this guess against `secret`.
async function playOneTurn(window, secret) {
  const doc = window.document;
  const tiles = Array.from(doc.querySelectorAll('.tile.active-row'));
  const guess = tiles.map(t => t.textContent).join('');
  // The true colours come from the page's own, separately tested code.
  const colours = window.eval(`feedbackToString(getFeedback(${JSON.stringify(guess)}, ${JSON.stringify(secret)}))`);
  colours.split('').forEach((c, i) => {
    const clicks = c === 'X' ? 0 : c === 'Y' ? 1 : 2; // grey, then yellow, then green
    for (let k = 0; k < clicks; k++) tiles[i].click();
  });
  doc.getElementById('confirm-btn').click();
  await wait(60); // the page handles a turn asynchronously, so give it a moment
  return guess;
}

async function openPage() {
  const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'https://example.com' });
  await wait(200);
  return dom.window;
}

(async () => {
  const window = await openPage();
  const doc = window.document;
  const status = doc.getElementById('status');

  let solved = false;
  for (let turn = 1; turn <= 6 && !solved; turn++) {
    const guess = await playOneTurn(window, 'stare');
    check(guess.length === 5, `turn ${turn}: expected a five letter suggestion, got "${guess}"`);
    solved = status.textContent.includes('Solved');
  }
  check(solved, `Assist me mode did not solve STARE within six guesses (status: "${status.textContent}")`);
  console.log(`PASS  Assist me mode: ${status.textContent}`);

  doc.getElementById('tab-auto').click();
  await wait(60);
  check(!doc.getElementById('auto-setup').hidden, 'the Watch it solve itself panel did not appear');
  doc.getElementById('secret-input').value = 'CRANE';
  doc.getElementById('start-auto-btn').click();
  for (let waited = 0; waited < 10000 && !/Solved|Out of guesses/.test(status.textContent); waited += 250) await wait(250);
  check(status.textContent.includes('Solved'), `automatic mode did not solve CRANE (status: "${status.textContent}")`);
  const played = Array.from(doc.querySelectorAll('.board-row'))
    .map(row => Array.from(row.querySelectorAll('.tile')).map(t => t.textContent).join(''))
    .filter(w => w.length === 5);
  check(played[played.length - 1] === 'crane', 'the last guess should be the secret word itself');
  console.log(`PASS  Watch it solve itself, with no clicks after Start: ${played.join(' -> ').toUpperCase()}`);
  console.log('All mode tests passed.');
})().catch(e => { console.error('FAIL  ' + e.message); process.exit(1); });
