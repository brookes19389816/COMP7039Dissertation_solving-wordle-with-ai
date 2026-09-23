// Checks the explanation panel in the real page: a short, plain template
// explanation when no API key is set, a working key box, and a clean
// fallback to the template if a live AI call fails, rather than an error
// message or an empty panel.
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
  const text = () => doc.getElementById('explain-text').textContent;
  const label = () => doc.getElementById('explain-source-tag').textContent;

  await playOneTurn(window, 'stare');
  check(label().includes('Template'), `expected the Template label, got "${label()}"`);
  check(text().startsWith('Guessed "RAISE"'), `unexpected explanation: "${text()}"`);
  check(!/bits|entropy/i.test(text()), 'the explanation should not use technical words like bits or entropy');
  check(text().split(/\s+/).length <= 40, 'the explanation should stay short');
  console.log(`PASS  Plain template explanation: ${text()}`);

  doc.getElementById('ai-key-toggle').click();
  doc.getElementById('api-key-input').value = 'sk-test-not-a-real-key';
  doc.getElementById('save-key-btn').click();
  const keyStatus = doc.getElementById('api-key-status').textContent;
  check(keyStatus.includes('session'), `the key box did not confirm the key (got "${keyStatus}")`);
  console.log('PASS  The key box accepts a key for this session only');

  // Make every live call fail, as it would with a bad key or no internet.
  window.fetch = async () => { throw new Error('no network in this test'); };
  doc.getElementById('new-game-btn').click();
  await wait(60);
  await playOneTurn(window, 'crane');
  await wait(300);
  check(label().includes('Template'), `after a failed live call the label should say Template, got "${label()}"`);
  check(text().startsWith('Guessed'), `after a failed live call an explanation should still be shown, got "${text()}"`);
  console.log('PASS  A failed live AI call falls back cleanly to the template');
  console.log('All explanation tests passed.');
})().catch(e => { console.error('FAIL  ' + e.message); process.exit(1); });
