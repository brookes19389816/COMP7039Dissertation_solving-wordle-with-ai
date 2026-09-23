// Checks that the page asks the AI only once for a situation it has
// already explained, by swapping the page's connection to the API for a
// stand in that counts requests and always gives the same reply.
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
  let requests = 0;
  window.fetch = async () => {
    requests++;
    return { ok: true, json: async () => ({ choices: [{ message: { content: 'A friendly test explanation.' } }] }) };
  };
  doc.getElementById('ai-key-toggle').click();
  doc.getElementById('api-key-input').value = 'sk-test-not-a-real-key';
  doc.getElementById('save-key-btn').click();

  const labels = [];
  for (let game = 1; game <= 2; game++) {
    doc.getElementById('new-game-btn').click();
    await wait(60);
    await playOneTurn(window, 'crane');
    await wait(200);
    labels.push(doc.getElementById('explain-source-tag').textContent);
  }
  check(labels.every(l => l.includes('Live AI')), `expected the Live AI label both times, got ${JSON.stringify(labels)}`);
  check(requests === 1, `expected exactly one request to the API, got ${requests}`);
  console.log('PASS  The same situation, explained twice, cost only one API request');
  console.log('All caching tests passed.');
})().catch(e => { console.error('FAIL  ' + e.message); process.exit(1); });
