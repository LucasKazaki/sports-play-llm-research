import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const PROJECT_ID = 'sports-play-llm';
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const STATE = resolve(ROOT, 'state/archit-doc-sync-state.json');
const count = value => Number.isSafeInteger(value) && value >= 0 ? value : null;
const timestamp = value => value === null || value === undefined ? null : typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(value) && Number.isFinite(Date.parse(value)) ? value : null;
const identifier = value => typeof value === 'string' && /^(?:[a-f0-9]{64}|[a-f0-9-]{36})$/i.test(value) ? value : null;
const phaseNames = ['monitoring', 'working', 'directing', 'queued', 'stopped', 'blocked', 'review', 'needs_human', 'verifying'];
const agentNames = new Set(['lab-director', 'qa', 'researcher', 'developer', 'workspace-writer', 'source-browser'].map(role => `${PROJECT_ID}-${role}`));

// Only these operational fields may enter the shared Doc. Never forward model
// prose, prompts, credentials, private media paths, transcripts, or raw receipts.
export function projectProgress(snapshot, company, frontierSnapshot) {
  const p = snapshot?.project;
  if (p?.id !== PROJECT_ID) throw new Error('Wrong or unavailable project snapshot');
  if (!Array.isArray(snapshot.tasks) || !Array.isArray(snapshot.events)) throw new Error('Incomplete project snapshot');
  const running = snapshot.tasks.filter(t => t.status === 'running');
  const counts = company?.projects?.find(item => item.id === PROJECT_ID)?.taskCounts;
  if (!counts || count(counts.running) === null || count(counts.review) === null || count(counts.blocked) === null) throw new Error('Authoritative full task counts unavailable');
  const diagnostic = company?.runtime?.loopDiagnostics?.find(d => d.projectId === PROJECT_ID);
  // The dedicated frontier endpoint uses full SQL dependency checks. The older
  // diagnostics projection counts active rows and is not a runnable-work source.
  if (frontierSnapshot?.project?.id !== PROJECT_ID) throw new Error('Wrong or unavailable frontier snapshot');
  const runnable = count(frontierSnapshot.frontier?.runnableTaskCount);
  const route = diagnostic?.effectiveExecution;
  const activeCalls = (company?.runtime?.activeCalls ?? []).filter(c => c.projectId === PROJECT_ID);
  const enabled = p.desired === true;
  const status = !enabled ? 'Stopped' : company.runtime?.started !== true ? 'Runtime not running' : counts.running || activeCalls.length ? 'Working' : runnable === null ? 'Queue state unknown' : runnable > 0 ? 'Queued' : 'Waiting for a useful research task';
  return {
    schemaVersion: 1,
    projectId: PROJECT_ID,
    enabled,
    runtimeStarted: company?.runtime?.started === true,
    status,
    phase: phaseNames.includes(p.phase) ? p.phase : 'unknown',
    runningTasks: counts.running,
    runnableTasks: runnable,
    activeAgentCalls: activeCalls.length,
    retainedReviewRows: counts.review ?? 0,
    retainedBlockedRows: counts.blocked ?? 0,
    lastVerifiedProgressAt: timestamp(p.lastVerifiedProgressAt),
    lastVerifiedProgressRef: identifier(p.lastVerifiedProgressRef),
    lastVerifiedProgressFamily: ['workspace_artifact', 'benchmark', 'native_effect', 'media', 'research_synthesis', 'public_source', 'legacy_verified'].includes(p.lastVerifiedProgressFamily) ? p.lastVerifiedProgressFamily : null,
    verifiedSequence: count(p.lastVerifiedProgressSequence),
    director: route ? { model: ['gpt-5.6-terra', 'loops-gtx1080-qwen3-4b', 'openai/gpt-oss-20b'].includes(route.model) ? route.model : 'unrecognized', provider: ['OpenAI via isolated Codex CLI', 'LM Studio', 'Hermes CLI'].includes(route.provider) ? route.provider : 'unrecognized' } : null,
    // Identifiers allow local audit without publishing unconstrained task prose.
    observedActiveTaskIds: running.map(t => identifier(t.id)).filter(Boolean).sort(),
    activeAgents: [...new Set(activeCalls.map(c => c.agentId).filter(id => agentNames.has(id)))].sort(),
    researchVerdict: 'SYSTEMS GO / SEMANTIC NO-GO',
    claimBoundary: 'Operational progress is not evidence of soccer accuracy, coach usefulness, or PhD-level novelty.',
  };
}

export function contentHash(progress) {
  return createHash('sha256').update(JSON.stringify(progress)).digest('hex');
}

async function fetchJson(path) {
  const response = await fetch(`http://127.0.0.1:4174${path}`, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`Runtime snapshot unavailable: HTTP ${response.status}`);
  return response.json();
}

async function main() {
  const args = process.argv.slice(2);
  const outputIndex = args.indexOf('--output');
  const [snapshot, company, frontier] = await Promise.all([fetchJson(`/api/company/projects/${PROJECT_ID}`), fetchJson('/api/company'), fetchJson(`/api/company/projects/${PROJECT_ID}/frontier`)]);
  const progress = projectProgress(snapshot, company, frontier);
  let prior = {};
  try { prior = JSON.parse(await readFile(STATE, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const result = { capturedAt: new Date().toISOString(), contentHash: contentHash(progress), progress };
  result.changedSincePublished = prior.publishedContentHash !== result.contentHash;
  if (outputIndex >= 0) {
    const path = resolve(args[outputIndex + 1]);
    await mkdir(dirname(path), { recursive: true });
    const temporary = `${path}.tmp-${process.pid}`;
    await writeFile(temporary, JSON.stringify(result, null, 2) + '\n', 'utf8');
    await rename(temporary, path);
  }
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
}
