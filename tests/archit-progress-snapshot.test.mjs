import test from 'node:test';
import assert from 'node:assert/strict';
import { projectProgress, contentHash } from '../scripts/archit-progress-snapshot.mjs';

function fixture() {
  return {
    snapshot: { project: { id: 'sports-play-llm', desired: true, phase: 'monitoring', lastProgressAt: 'activity-only', lastVerifiedProgressAt: '2026-09-07T00:00:00Z', lastVerifiedProgressRef: 'a'.repeat(64) }, tasks: [{ id: 't', status: 'review', description: 'PRIVATE TRANSCRIPT' }], events: [] },
    frontier: { project: { id: 'sports-play-llm' }, frontier: { runnableTaskCount: 0 } },
    company: { projects: [{ id: 'sports-play-llm', taskCounts: { running: 0, review: 1, blocked: 0 } }], runtime: { started: true, activeCalls: [], loopDiagnostics: [{ projectId: 'sports-play-llm', runnableTaskCount: 0 }] } },
  };
}
test('monitoring and activity cannot impersonate verified research progress', () => {
  const { snapshot, company, frontier } = fixture();
  const p = projectProgress(snapshot, company, frontier);
  assert.equal(p.status, 'Waiting for a useful research task');
  assert.equal(p.lastVerifiedProgressAt, '2026-09-07T00:00:00Z');
  assert.equal(p.retainedReviewRows, 1);
  assert.equal(p.runnableTasks, 0);
  assert.equal(JSON.stringify(p).includes('PRIVATE'), false);
  assert.equal(JSON.stringify(p).includes('activity-only'), false);
});
test('bounded task history cannot undercount full runtime work or backlog', () => {
  const { snapshot, company, frontier } = fixture();
  company.projects[0].taskCounts = { running: 3, review: 59, blocked: 91 };
  const p = projectProgress(snapshot, company, frontier);
  assert.equal(p.runningTasks, 3);
  assert.equal(p.retainedReviewRows, 59);
  assert.equal(p.retainedBlockedRows, 91);
  assert.equal(p.status, 'Working');
  delete company.projects;
  assert.throws(() => projectProgress(snapshot, company, frontier), /Authoritative/);
});
test('legacy diagnostics and dependency-blocked ready rows cannot invent runnable work', () => {
  const { snapshot, company, frontier } = fixture();
  company.runtime.loopDiagnostics[0].runnableTaskCount = 7;
  snapshot.tasks.push({ id: 'waiting-dependency', status: 'ready', dependsOn: ['missing'] });
  assert.equal(projectProgress(snapshot, company, frontier).runnableTasks, 0);
  assert.equal(projectProgress(snapshot, company, frontier).status, 'Waiting for a useful research task');
});
test('unrelated projects and blocked rows cannot become soccer work', () => {
  const { snapshot, company, frontier } = fixture();
  company.runtime.activeCalls = [{ projectId: 'other', agentId: 'secret' }];
  snapshot.tasks.push({ id: 'blocked', status: 'blocked' });
  assert.equal(projectProgress(snapshot, company, frontier).activeAgentCalls, 0);
  assert.equal(projectProgress(snapshot, company, frontier).status, 'Waiting for a useful research task');
  snapshot.project.id = 'other';
  assert.throws(() => projectProgress(snapshot, company, frontier), /Wrong/);
});
test('missing runnable evidence is unknown, not zero or success', () => {
  const { snapshot, company, frontier } = fixture();
  frontier.frontier = {};
  assert.equal(projectProgress(snapshot, company, frontier).runnableTasks, null);
  assert.equal(projectProgress(snapshot, company, frontier).status, 'Queue state unknown');
  assert.throws(() => projectProgress({ project: snapshot.project }, company, frontier), /Incomplete/);
});
test('bounded event history and unrelated waits are not advertised as a future source check', () => {
  const { snapshot, company, frontier } = fixture();
  snapshot.events = [{ status: 'claimed', availableAt: '2020-01-01', payload: { reason: 'public-source-change-revalidation' } }];
  company.runtime.loopDiagnostics[0].intentionalWait = { kind: 'human_gate', until: '2099-01-01' };
  assert.equal('nextSourceCheckAt' in projectProgress(snapshot, company, frontier), false);
});
test('stable projection deduplicates activity timestamps but notices verified changes', () => {
  const { snapshot, company, frontier } = fixture();
  const initial = contentHash(projectProgress(snapshot, company, frontier));
  snapshot.project.lastProgressAt = 'new-activity';
  assert.equal(contentHash(projectProgress(snapshot, company, frontier)), initial);
  snapshot.project.lastVerifiedProgressRef = 'b'.repeat(64);
  assert.notEqual(contentHash(projectProgress(snapshot, company, frontier)), initial);
});
test('unexpected objects and unrestricted prose cannot cross the status boundary', () => {
  const { snapshot, company, frontier } = fixture();
  snapshot.project.phase = 'PRIVATE TRANSCRIPT';
  snapshot.project.lastVerifiedProgressAt = 'PRIVATE TRANSCRIPT';
  snapshot.project.lastVerifiedProgressRef = 'PRIVATE TRANSCRIPT';
  company.runtime.loopDiagnostics[0].effectiveExecution = { model: 'PRIVATE TRANSCRIPT', provider: 'PRIVATE TRANSCRIPT' };
  assert.equal(JSON.stringify(projectProgress(snapshot, company, frontier)).includes('PRIVATE'), false);
  company.projects[0].taskCounts.review = { secret: 'PRIVATE TRANSCRIPT' };
  assert.throws(() => projectProgress(snapshot, company, frontier), /Authoritative/);
});
test('actual active calls and runnable evidence are distinguished', () => {
  const { snapshot, company, frontier } = fixture();
  frontier.frontier.runnableTaskCount = 2;
  assert.equal(projectProgress(snapshot, company, frontier).status, 'Queued');
  company.runtime.activeCalls = [{ projectId: 'sports-play-llm', agentId: 'reviewer' }];
  assert.equal(projectProgress(snapshot, company, frontier).status, 'Working');
  snapshot.project.desired = false;
  assert.equal(projectProgress(snapshot, company, frontier).status, 'Stopped');
});
