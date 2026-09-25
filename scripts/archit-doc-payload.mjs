import { createHash } from 'node:crypto';
import { readFile, writeFile, rename, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { contentHash } from './archit-progress-snapshot.mjs';

export const DOCUMENT_ID = '1uUdenRhHnkKJQSQVH4ppDhSdTbrlLJafrAuiZMzKEjk';
export const TAB_ID = 't.0';
export const RANGE_NAME = 'SOCCER_LIVE_STATUS_V1';
const statuses = new Set(['Stopped', 'Runtime not running', 'Working', 'Queued', 'Queue state unknown', 'Waiting for a useful research task']);
const models = new Set(['gpt-5.6-terra', 'loops-gtx1080-qwen3-4b', 'openai/gpt-oss-20b', 'unrecognized']);
const providers = new Set(['OpenAI via isolated Codex CLI', 'LM Studio', 'Hermes CLI', 'unrecognized']);
const families = new Set(['workspace_artifact', 'benchmark', 'native_effect', 'media', 'research_synthesis', 'public_source', 'legacy_verified']);
const ensure = (ok, message) => { if (!ok) throw new Error(message); };
const count = n => { ensure(Number.isSafeInteger(n) && n >= 0, 'Invalid count'); return String(n); };
function instant(value) {
  ensure(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(value), 'Invalid UTC timestamp');
  const date = new Date(value);
  ensure(Number.isFinite(date.getTime()) && date.toISOString().slice(0, 19) === value.slice(0, 19), 'Invalid UTC date');
  return date;
}
// Google requires timeZoneId to be absent for date-only chips. The timestamp
// remains UTC and the adjacent clock explicitly names UTC.
const chip = value => ({ timestamp: instant(value).toISOString(), locale: 'en', dateFormat: 'DATE_FORMAT_MONTH_DAY_YEAR_ABBREVIATED', timeFormat: 'TIME_FORMAT_DISABLED' });
const clock = value => instant(value).toISOString().slice(11, 19) + ' UTC';

export function liveParts(snapshot) {
  if (snapshot?.sourceUnavailable === true) {
    ensure(snapshot.contentHash === contentHash({ sourceUnavailable: true, priorHash: snapshot.previousSnapshot?.contentHash ?? null }), 'Unavailable snapshot hash mismatch');
    ensure(!snapshot.previousSnapshot?.sourceUnavailable, 'Nested unavailable snapshots are invalid');
    if (snapshot.previousSnapshot) liveParts(snapshot.previousSnapshot);
    const prior = snapshot.previousSnapshot;
    const parts = ['Live progress\nFailed runtime check: ', chip(snapshot.capturedAt), ' at ' + clock(snapshot.capturedAt) + '. No fresh runtime snapshot.\nLast successful runtime snapshot: '];
    if (prior) parts.push(chip(prior.capturedAt), ' at ' + clock(prior.capturedAt));
    else parts.push('unavailable');
    parts.push('.\nLast runtime-verified delivery: ');
    if (prior?.progress.lastVerifiedProgressAt) parts.push(chip(prior.progress.lastVerifiedProgressAt), ' at ' + clock(prior.progress.lastVerifiedProgressAt));
    else parts.push('unavailable');
    parts.push('.\nSYSTEMS GO / SEMANTIC NO-GO. No current activity or scientific progress is inferred while the source is unavailable.\nTarget check cadence: one minute. Scheduled checks depend on this computer and Codex being available and may be delayed by active work.\n\n');
    return parts;
  }
  const p = snapshot?.progress;
  ensure(p?.projectId === 'sports-play-llm' && p.schemaVersion === 1, 'Wrong snapshot');
  ensure(snapshot.contentHash === contentHash(p), 'Snapshot semantic hash mismatch');
  ensure(statuses.has(p.status), 'Invalid status');
  const route = p.director;
  ensure(!route || (models.has(route.model) && providers.has(route.provider)), 'Unapproved route text');
  ensure(p.lastVerifiedProgressFamily === null || families.has(p.lastVerifiedProgressFamily), 'Unapproved delivery category');
  const parts = ['Live progress\nRuntime observed: ', chip(snapshot.capturedAt), ' at ' + clock(snapshot.capturedAt) + '.\n'];
  parts.push('Runtime: ' + p.status + '.\n');
  parts.push('Activity: ' + count(p.runningTasks) + ' running tasks; ' + (p.runnableTasks === null ? 'unknown' : count(p.runnableTasks)) + ' runnable tasks; ' + count(p.activeAgentCalls) + ' active calls.\n');
  parts.push('Director route: ' + (route ? route.model + ' / ' + route.provider : 'unavailable') + '. This is routing state, not a completed model run.\n');
  parts.push('Last runtime-verified delivery: ');
  if (p.lastVerifiedProgressAt) parts.push(chip(p.lastVerifiedProgressAt), ' at ' + clock(p.lastVerifiedProgressAt));
  else parts.push('unavailable');
  parts.push('; category ' + (p.lastVerifiedProgressFamily || 'unspecified') + '.\n');
  parts.push('Retained task records: ' + count(p.retainedReviewRows) + ' in review; ' + count(p.retainedBlockedRows) + ' blocked. These are backlog records, not completed research.\n');
  parts.push('SYSTEMS GO / SEMANTIC NO-GO. Runtime-verified delivery may establish only structural or systems evidence; it does not establish soccer accuracy, coach utility or doctoral novelty.\n');
  parts.push('Target check cadence: one minute. Scheduled checks depend on this computer and Codex being available and may be delayed by active work. Only changed snapshots are published. Observation time precedes the Doc write; publication success is recorded separately after readback.\n\n');
  return parts;
}

export function targetTab(document) {
  ensure(document?.documentId === DOCUMENT_ID && document.revisionId, 'Wrong document or missing revision');
  const tabs = document.tabs?.filter(t => t.tabId === TAB_ID);
  ensure(tabs?.length === 1 && Array.isArray(tabs[0].body?.content), 'Missing or ambiguous target tab');
  return tabs[0];
}

export function managedRange(document) {
  const tab = targetTab(document);
  const matches = Object.values(tab.namedRanges || {}).flatMap(group => group.namedRanges || []).filter(r => r.name === RANGE_NAME);
  ensure(matches.length === 1 && matches[0].ranges?.length === 1, 'Missing or ambiguous managed range');
  const named = matches[0], range = named.ranges[0];
  ensure(named.namedRangeId && (range.tabId === undefined || range.tabId === TAB_ID), 'Invalid range identity');
  ensure(Number.isSafeInteger(range.startIndex) && range.startIndex > 0 && Number.isSafeInteger(range.endIndex) && range.endIndex > range.startIndex, 'Invalid range bounds');
  const content = tab.body.content;
  ensure(content.some(p => p.startIndex === range.startIndex && p.paragraph) && content.some(p => p.endIndex === range.endIndex && p.paragraph), 'Managed range must span complete paragraphs');
  return { namedRangeId: named.namedRangeId, startIndex: range.startIndex, endIndex: range.endIndex, tabId: TAB_ID };
}

export function insertion(snapshot, startIndex) {
  ensure(Number.isSafeInteger(startIndex) && startIndex > 0, 'Invalid insertion index');
  let index = startIndex;
  const requests = [];
  for (const part of liveParts(snapshot)) {
    if (typeof part === 'string') {
      requests.push({ insertText: { location: { index, tabId: TAB_ID }, text: part } });
      index += part.length;
    } else {
      requests.push({ insertDate: { location: { index, tabId: TAB_ID }, dateElementProperties: part } });
      index += 1;
    }
  }
  const range = { startIndex, endIndex: index, tabId: TAB_ID };
  requests.push({ createNamedRange: { name: RANGE_NAME, range } });
  requests.push({ updateTextStyle: { range, textStyle: { bold: false, italic: false, underline: false, fontSize: { magnitude: 11, unit: 'PT' }, weightedFontFamily: { fontFamily: 'Arial' }, foregroundColor: { color: { rgbColor: { red: 0, green: 0, blue: 0 } } } }, fields: 'bold,italic,underline,fontSize,weightedFontFamily,foregroundColor,link' } });
  requests.push({ updateParagraphStyle: { range, paragraphStyle: { namedStyleType: 'NORMAL_TEXT', lineSpacing: 115, spaceAbove: { magnitude: 0, unit: 'PT' }, spaceBelow: { magnitude: 5, unit: 'PT' }, indentStart: { magnitude: 0, unit: 'PT' }, indentEnd: { magnitude: 0, unit: 'PT' }, indentFirstLine: { magnitude: 0, unit: 'PT' }, keepWithNext: false }, fields: 'namedStyleType,lineSpacing,spaceAbove,spaceBelow,indentStart,indentEnd,indentFirstLine,keepWithNext' } });
  requests.push({ deleteParagraphBullets: { range } });
  const heading = { startIndex, endIndex: startIndex + 'Live progress'.length, tabId: TAB_ID };
  requests.push({ updateTextStyle: { range: heading, textStyle: { bold: true, fontSize: { magnitude: 14, unit: 'PT' } }, fields: 'bold,fontSize' } });
  requests.push({ updateParagraphStyle: { range: heading, paragraphStyle: { keepWithNext: true, spaceAbove: { magnitude: 10, unit: 'PT' }, spaceBelow: { magnitude: 4, unit: 'PT' } }, fields: 'keepWithNext,spaceAbove,spaceBelow' } });
  return { requests, range };
}

export function unavailableSnapshot(previousSnapshot, failedAt = new Date().toISOString()) {
  ensure(!previousSnapshot?.sourceUnavailable, 'Prior snapshot must be a successful runtime read');
  if (previousSnapshot) liveParts(previousSnapshot);
  instant(failedAt);
  return { sourceUnavailable: true, capturedAt: failedAt, previousSnapshot: previousSnapshot || null, contentHash: contentHash({ sourceUnavailable: true, priorHash: previousSnapshot?.contentHash ?? null }) };
}

export function prepareReplacement(document, snapshot, state, now = Date.now()) {
  const age = now - instant(snapshot.capturedAt).getTime();
  ensure(age >= -5000 && age < 120000, 'Snapshot is stale or from the future; capture again');
  const previous = managedRange(document);
  ensure(state?.documentId === DOCUMENT_ID && state.managedContentHash, 'Missing acknowledged managed-content state');
  const currentHash = managedContentHash(document);
  const desiredHash = signatureHash(liveParts(snapshot));
  ensure(currentHash === state.managedContentHash || currentHash === desiredHash, 'Collaborator change inside managed range; preserve and reconcile');
  if (state.publishedContentHash === snapshot.contentHash && currentHash === state.managedContentHash) return { skip: true, reason: 'Unchanged snapshot; current managed content verified', documentId: DOCUMENT_ID, documentRevision: document.revisionId };
  if (currentHash === desiredHash) return { skip: true, recoverAcknowledgment: true, reason: 'Desired payload already present', ...verifyReadback(document, snapshot) };
  const next = insertion(snapshot, previous.startIndex);
  return { document_id: DOCUMENT_ID, write_control: { requiredRevisionId: document.revisionId }, requests: [
    { deleteNamedRange: { namedRangeId: previous.namedRangeId, tabsCriteria: { tabIds: [TAB_ID] } } },
    { deleteContentRange: { range: { startIndex: previous.startIndex, endIndex: previous.endIndex, tabId: TAB_ID } } },
    ...next.requests,
  ] };
}

function stripIndexes(value) {
  if (Array.isArray(value)) return value.map(stripIndexes);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).filter(([k]) => !['startIndex', 'endIndex'].includes(k)).map(([k, v]) => [k, stripIndexes(v)]));
  return value;
}
export function outsideFingerprint(document, range = managedRange(document)) {
  const content = targetTab(document).body.content.filter(p => (p.endIndex ?? 0) <= range.startIndex || (p.startIndex ?? 0) >= range.endIndex);
  return createHash('sha256').update(JSON.stringify(stripIndexes(content))).digest('hex');
}
function observedParts(document) {
  const range = managedRange(document);
  const observed = [];
  for (const p of targetTab(document).body.content) {
    if ((p.endIndex ?? 0) <= range.startIndex || (p.startIndex ?? 0) >= range.endIndex) continue;
    ensure(p.paragraph, 'Unexpected managed content');
    const hasSuggestions = value => value && typeof value === 'object' && Object.entries(value).some(([key, child]) => (key.startsWith('suggested') && child && Object.keys(child).length > 0) || hasSuggestions(child));
    ensure(!hasSuggestions(p), 'Unresolved suggestions in managed content');
    for (const e of p.paragraph.elements) {
      ensure(!e.suggestedInsertionIds?.length && !e.suggestedDeletionIds?.length, 'Unresolved suggestions in managed content');
      ensure(!e.textRun?.textStyle?.link && !e.dateElement?.textStyle?.link, 'Collaborator link in link-free managed template');
      if (e.textRun) observed.push(e.textRun.content);
      else if (e.dateElement) {
        const value = e.dateElement.dateElementProperties;
        ensure(value && !value.timeZoneId && value.locale === 'en' && value.dateFormat === 'DATE_FORMAT_MONTH_DAY_YEAR_ABBREVIATED' && value.timeFormat === 'TIME_FORMAT_DISABLED', 'Native date properties mismatch');
        observed.push(chip(value.timestamp));
      } else throw new Error('Unexpected native element in managed content');
    }
  }
  return observed;
}
const signature = parts => parts.map(p => typeof p === 'string' ? p : '\uFFFC' + JSON.stringify(p) + '\uFFFC').join('');
const signatureHash = parts => createHash('sha256').update(signature(parts)).digest('hex');
export function managedContentHash(document) { return signatureHash(observedParts(document)); }
export function verifyReadback(document, snapshot, before = null) {
  const range = managedRange(document);
  ensure(signature(observedParts(document)) === signature(liveParts(snapshot)), 'Managed content readback mismatch');
  if (before) ensure(outsideFingerprint(before) === outsideFingerprint(document), 'Content outside managed range changed');
  return { verified: true, documentId: DOCUMENT_ID, documentRevision: document.revisionId, managedRangeName: RANGE_NAME, managedRangeId: range.namedRangeId, managedContentHash: managedContentHash(document), publishedContentHash: snapshot.contentHash, snapshotCapturedAt: snapshot.capturedAt, sourceUnavailable: snapshot.sourceUnavailable === true, lastPublishedRuntimeSnapshot: snapshot.sourceUnavailable ? snapshot.previousSnapshot : snapshot, lastSuccessfulDocVerificationAt: new Date().toISOString() };
}

async function json(path) { return JSON.parse((await readFile(path, 'utf8')).replace(/^\uFEFF/, '')); }
async function atomic(path, value) {
  await mkdir(dirname(path), { recursive: true });
  const temporary = path + '.tmp-' + process.pid;
  await writeFile(temporary, JSON.stringify(value, null, 2) + '\n', 'utf8');
  await rename(temporary, path);
}
async function main() {
  const args = process.argv.slice(2), mode = args[0];
  const option = name => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };
  ensure(['prepare', 'verify'].includes(mode) && option('--snapshot') && option('--document'), 'Use prepare|verify --snapshot path --document path [--before path] [--output path] [--ack-state path]');
  const snapshot = await json(option('--snapshot')), document = await json(option('--document'));
  ensure(mode !== 'prepare' || option('--state'), 'prepare requires --state with last acknowledged managed-content hash');
  const result = mode === 'prepare' ? prepareReplacement(document, snapshot, await json(option('--state'))) : verifyReadback(document, snapshot, option('--before') ? await json(option('--before')) : null);
  if (option('--ack-state')) {
    ensure(mode === 'verify' && option('--before'), 'Acknowledgment requires verified before/after');
    let prior = {};
    try { prior = await json(option('--ack-state')); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    await atomic(option('--ack-state'), { ...prior, ...result });
  }
  if (option('--output')) await atomic(option('--output'), result);
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(error => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
