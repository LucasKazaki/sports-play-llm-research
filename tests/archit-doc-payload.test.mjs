import test from 'node:test';
import assert from 'node:assert/strict';
import { contentHash } from '../scripts/archit-progress-snapshot.mjs';
import { DOCUMENT_ID, TAB_ID, RANGE_NAME, liveParts, insertion, prepareReplacement, verifyReadback, unavailableSnapshot } from '../scripts/archit-doc-payload.mjs';

function snapshot(running = 1) {
  const progress = { schemaVersion: 1, projectId: 'sports-play-llm', status: running ? 'Working' : 'Waiting for a useful research task', runningTasks: running, runnableTasks: 0, activeAgentCalls: running, retainedReviewRows: 3, retainedBlockedRows: 9, director: { model: 'gpt-5.6-terra', provider: 'OpenAI via isolated Codex CLI' }, lastVerifiedProgressAt: '2026-09-07T03:00:00Z', lastVerifiedProgressFamily: 'workspace_artifact' };
  return { capturedAt: '2026-09-07T05:00:00.000Z', contentHash: contentHash(progress), progress };
}
function nativeDocument(s) {
  let index = 1, paragraphStart = 1, elements = [];
  const content = [{ endIndex: 1, sectionBreak: {} }];
  const append = part => {
    if (typeof part !== 'string') { elements.push({ startIndex: index, endIndex: ++index, dateElement: { dateElementProperties: part } }); return; }
    for (const text of part.match(/[^\n]*\n|[^\n]+/g) || []) {
      elements.push({ startIndex: index, endIndex: index + text.length, textRun: { content: text, textStyle: {} } });
      index += text.length;
      if (text.endsWith('\n')) { content.push({ startIndex: paragraphStart, endIndex: index, paragraph: { elements, paragraphStyle: {} } }); elements = []; paragraphStart = index; }
    }
  };
  append('Preserve intro.\n');
  const startIndex = index;
  liveParts(s).forEach(append);
  const endIndex = index;
  append('Preserve collaborator research notes.\n');
  return { documentId: DOCUMENT_ID, revisionId: 'current-revision', tabs: [{ tabId: TAB_ID, body: { content }, namedRanges: { [RANGE_NAME]: { namedRanges: [{ name: RANGE_NAME, namedRangeId: 'managed-id', ranges: [{ startIndex, endIndex, tabId: TAB_ID }] }] } } }] };
}
const now = Date.parse('2026-09-07T05:00:00Z');
test('native date insertion uses one UTF-16 unit and full paragraph range', () => {
  const s = snapshot(), result = insertion(s, 16);
  assert.equal(result.requests.filter(r => r.insertDate).length, 2);
  assert.ok(result.requests.filter(r => r.insertDate).every(r => !('timeZoneId' in r.insertDate.dateElementProperties)));
  assert.equal(result.range.endIndex, 16 + liveParts(s).reduce((n, p) => n + (typeof p === 'string' ? p.length : 1), 0));
  assert.equal(verifyReadback(nativeDocument(s), s).verified, true);
});
test('changed status replaces only observed named range with revision protection', () => {
  const old = nativeDocument(snapshot()), state = verifyReadback(old, snapshot());
  const next = snapshot(0), request = prepareReplacement(old, next, state, now);
  assert.deepEqual(request.write_control, { requiredRevisionId: 'current-revision' });
  assert.equal(request.requests[0].deleteNamedRange.namedRangeId, 'managed-id');
  assert.equal(request.requests[1].deleteContentRange.range.startIndex, 17);
  assert.equal(verifyReadback(nativeDocument(next), next, old).verified, true);
});
test('collaborator edit inside managed block blocks overwrite', () => {
  const doc = nativeDocument(snapshot()), state = verifyReadback(doc, snapshot());
  const run = doc.tabs[0].body.content.flatMap(p => p.paragraph?.elements || []).find(e => e.textRun?.content.includes('Runtime:'));
  run.textRun.content = run.textRun.content.replace('Working', 'Changed');
  assert.throws(() => prepareReplacement(doc, snapshot(0), state, now), /Collaborator change/);
});
test('outside collaborator text must survive readback', () => {
  const before = nativeDocument(snapshot()), after = nativeDocument(snapshot(0));
  after.tabs[0].body.content.at(-1).paragraph.elements[0].textRun.content = 'Changed outside content.\n';
  assert.throws(() => verifyReadback(after, snapshot(0), before), /outside managed range/);
});
test('unchanged snapshot checks remote content and skips mutation', () => {
  const s = snapshot(), doc = nativeDocument(s), state = verifyReadback(doc, s);
  assert.equal(prepareReplacement(doc, s, state, now).skip, true);
  delete doc.tabs[0].namedRanges;
  assert.throws(() => prepareReplacement(doc, s, state, now), /Missing or ambiguous/);
});
test('already-published payload can recover an interrupted acknowledgment', () => {
  const prior = verifyReadback(nativeDocument(snapshot()), snapshot()), next = snapshot(0);
  assert.equal(prepareReplacement(nativeDocument(next), next, prior, now).recoverAcknowledgment, true);
});
test('wrong document, duplicate range, stale snapshot and unacknowledged state fail closed', () => {
  const s = snapshot(), doc = nativeDocument(s), state = verifyReadback(doc, s);
  assert.throws(() => prepareReplacement(doc, s, state, now + 120000), /stale/);
  assert.throws(() => prepareReplacement(doc, s, {}, now), /acknowledged/);
  doc.documentId = 'wrong';
  assert.throws(() => verifyReadback(doc, s), /Wrong document/);
  doc.documentId = DOCUMENT_ID;
  doc.tabs[0].namedRanges[RANGE_NAME].namedRanges.push(doc.tabs[0].namedRanges[RANGE_NAME].namedRanges[0]);
  assert.throws(() => prepareReplacement(doc, s, state, now), /ambiguous/);
});
test('malformed or raw agent fields cannot become published text', () => {
  const s = snapshot(); s.progress.director.model = 'PRIVATE TRANSCRIPT'; s.contentHash = contentHash(s.progress);
  assert.throws(() => liveParts(s), /Unapproved/);
  const countBad = snapshot(); countBad.progress.runningTasks = '2'; countBad.contentHash = contentHash(countBad.progress);
  assert.throws(() => liveParts(countBad), /Invalid count/);
  const tampered = snapshot(); tampered.progress.activeAgentCalls++;
  assert.throws(() => liveParts(tampered), /hash mismatch/);
});
test('source failure dates the failed check separately and retains prior evidence time', () => {
  const prior = snapshot(), failed = unavailableSnapshot(prior, '2026-09-07T05:05:00Z');
  const parts = liveParts(failed), text = parts.filter(p => typeof p === 'string').join('');
  assert.match(text, /Failed runtime check:/);
  assert.match(text, /05:05:00 UTC/);
  assert.match(text, /Last successful runtime snapshot:.*05:00:00 UTC/s);
  assert.match(text, /03:00:00 UTC/);
  assert.doesNotMatch(text, /running tasks|Runtime: Working/);
  assert.equal(verifyReadback(nativeDocument(failed), failed).lastPublishedRuntimeSnapshot.contentHash, prior.contentHash);
});
test('first source failure has no invented prior snapshot or delivery timestamp', () => {
  const s = unavailableSnapshot(null, '2026-09-07T05:05:00Z');
  const parts = liveParts(s), text = parts.filter(p => typeof p === 'string').join('');
  assert.match(text, /Last successful runtime snapshot: unavailable/);
  assert.match(text, /Last runtime-verified delivery: unavailable/);
  assert.equal(parts.filter(p => typeof p === 'object').length, 1);
  assert.equal(verifyReadback(nativeDocument(s), s).verified, true);
});
test('native date mismatch cannot be acknowledged as text-only success', () => {
  const s = snapshot(), doc = nativeDocument(s);
  const date = doc.tabs[0].body.content.flatMap(p => p.paragraph?.elements || []).find(e => e.dateElement);
  date.dateElement.dateElementProperties.timestamp = '2026-09-08T05:00:00Z';
  assert.throws(() => verifyReadback(doc, s), /readback mismatch/);
});
test('collaborator links and unresolved native suggestions are preserved by refusing replacement', () => {
  for (const edit of ['link', 'suggestion']) {
    const s = snapshot(), doc = nativeDocument(s), state = verifyReadback(doc, s);
    const run = doc.tabs[0].body.content[2].paragraph.elements[0].textRun;
    if (edit === 'link') run.textStyle.link = { url: 'https://example.com/collaborator-source' };
    else run.suggestedTextStyleChanges = { pending: { textStyle: { bold: true }, textStyleSuggestionState: { boldSuggested: true } } };
    assert.throws(() => prepareReplacement(doc, snapshot(0), state, now), /Collaborator link|Unresolved suggestions/);
  }
});
