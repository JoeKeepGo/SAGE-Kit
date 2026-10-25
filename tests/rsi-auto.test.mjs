import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pathToFileURL } from 'node:url';
const { openRSI } = await import(process.env.SAGE_AGENT_ADAPTER_DIR ? pathToFileURL(join(process.env.SAGE_AGENT_ADAPTER_DIR, 'rsi.mjs')) : '../adapters/rsi.mjs');
const exec = promisify(execFile);
const opts = { timeout: 60000, skip: process.platform === 'win32' ? 'Fixed evaluator process cleanup requires POSIX' : false };
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

async function fixture(t, { metric = false, maxRounds = 3, postFailure = false, policy: policyPatch = {}, evaluator } = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-rsi-auto-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = (name, value) => writeFile(join(root, name), value);
  const git = (...args) => exec('/usr/bin/git', args, { cwd: root, timeout: 3000, maxBuffer: 8192, env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1' } });
  await put('.gitignore', 'state/\nregression.flag\n');
  await put('authority.md', 'Only target.txt may change. Human acceptance remains required.');
  await put('feedback.txt', 'Actual fixed check reports initial failure or lower metric.');
  await put('target.txt', metric ? '1' : 'BAD');
  await put('check.mjs', evaluator ?? `import {readFileSync,existsSync} from 'node:fs';
const value=readFileSync('target.txt','utf8');
${metric ? "console.log(JSON.stringify({metrics:{score:Number(value)}}));" : "if(value!=='GOOD')process.exitCode=3;"}
if(process.cwd()===${JSON.stringify(root)} && (${postFailure} || existsSync('regression.flag'))) process.exitCode=7;`);
  const plan = { version: 1, authority: ['authority.md'], inputs: ['check.mjs', 'target.txt'], targets: ['target.txt'], command: [process.execPath, 'check.mjs'], expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, maxEvaluations: 3, timeoutMs: 2000, maxOutputBytes: 4096 };
  const planBytes = JSON.stringify(plan);
  await put('plan.json', planBytes);
  await git('init', '-b', 'main');
  await git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'add', '.');
  await git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Fixed evaluation fixture');
  await git('checkout', '-b', 'workflow/auto-fixture');
  const policy = { branch: 'workflow/auto-fixture', baseBranch: 'main', planSha256: hash(planBytes), maxRounds, improvement: metric ? { kind: 'metric', name: 'score', direction: 'increase', minDelta: 1 } : { kind: 'repair' }, ...policyPatch };
  const config = { root, planPath: 'plan.json', statePath: 'state/rsi.json', automaticPolicy: policy };
  const api = await openRSI(config);
  const candidate = content => ({ hypothesis: 'Repair the observed defect or improve the measured score', feedback: [{ path: 'feedback.txt', kind: 'failure' }], files: [{ path: 'target.txt', content: content ?? (metric ? '2' : 'GOOD') }] });
  const evaluate = async content => { await api.propose(candidate(content)); return api.evaluate(); };
  const target = () => readFile(join(root, 'target.txt'), 'utf8');
  return { root, put, git, plan, policy, config, api, candidate, evaluate, target };
}

test('repair adopts actual files, runs a real postcheck and records preauthorization without human approval', opts, async t => {
  const f = await fixture(t), result = await f.evaluate();
  assert.equal(result.status, 'adopted'); assert.equal(await f.target(), 'GOOD');
  assert.deepEqual(result.evaluation.runs.map(r => r.exitCode), [3, 0]);
  assert.equal(result.postchecks[0].run.exitCode, 0);
  assert.equal(result.approval.source, 'preauthorized-project-policy');
  assert.equal(result.approval.policyDigest, result.automatic.policyDigest);
  await assert.rejects(f.api.adopt({ authorize: () => true }), { code: 'E_RSI_AUTOMATIC' });
  const rolled = await f.api.rollback(); assert.equal(rolled.status, 'rolled_back'); assert.equal(await f.target(), 'BAD');
  t.diagnostic(JSON.stringify({ resourceEvidence: 'automatic repair and explicit policy rollback', evaluateIO: result.io, rollbackIO: rolled.io, fixedRunDurationMs: [...result.evaluation.runs.map(r => r.durationMs), result.postchecks[0].run.durationMs] }));
});

test('actual cwd post-adoption failure restores original files and records both outcomes', opts, async t => {
  const f = await fixture(t, { postFailure: true }), result = await f.evaluate();
  assert.equal(result.status, 'rolled_back'); assert.equal(await f.target(), 'BAD');
  assert.equal(result.evaluation.improvement.passed, true); assert.equal(result.postchecks[0].run.exitCode, 7);
  assert.equal(result.automatic.consecutiveFailures, 1);
  t.diagnostic(JSON.stringify({ resourceEvidence: 'evaluate including failed postcheck and automatic rollback', io: result.io, fixedRunDurationMs: [...result.evaluation.runs.map(r => r.durationMs), result.postchecks[0].run.durationMs] }));
});

test('explicit observation detects a later regression and rolls back without polling', opts, async t => {
  const f = await fixture(t); await f.evaluate(); await f.put('regression.flag', 'regression');
  const result = await f.api.observe(); assert.equal(result.status, 'rolled_back'); assert.equal(await f.target(), 'BAD');
  assert.equal(result.postchecks.length, 2);
});

test('observation preserves third-party target changes and refuses rollback on conflict', opts, async t => {
  const f = await fixture(t); await f.evaluate(); await f.put('target.txt', 'THIRD PARTY');
  await assert.rejects(f.api.observe(), { code: 'E_RSI_CONFLICT' });
  await assert.rejects(f.api.rollback(), { code: 'E_RSI_CONFLICT' }); assert.equal(await f.target(), 'THIRD PARTY');
});

test('metric gains advance bounded rounds across normal branch commits and keep flat complete history', opts, async t => {
  const f = await fixture(t, { metric: true, maxRounds: 2 });
  assert.equal((await f.evaluate('2')).status, 'adopted');
  await f.git('add', 'target.txt'); await f.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Accept completed local development round');
  const result = await f.evaluate('3'); assert.equal(result.status, 'adopted'); assert.equal(result.next, 'stop');
  assert.equal(result.automatic.history.length, 1); assert.equal(result.automatic.round, 2);
  const state = JSON.parse(await readFile(join(f.root, 'state/rsi.json'), 'utf8'));
  assert.equal(state.automatic.history[0].state.postchecks[0].passed, true);
  assert.equal(state.automatic.history[0].state.automatic, undefined);
  await assert.rejects(f.api.propose(f.candidate('4')), { code: 'E_RSI_AUTO_STOP' });
});

test('two consecutive metric non-gains stop the window without adoption', opts, async t => {
  const f = await fixture(t, { metric: true });
  assert.equal((await f.evaluate('0')).status, 'evaluated');
  const result = await f.evaluate('-1'); assert.equal(result.status, 'evaluated'); assert.equal(result.next, 'stop');
  assert.equal(result.automatic.consecutiveFailures, 2); assert.equal(await f.target(), '1');
});

test('successful repair is not adopted when baseline already passes', opts, async t => {
  const f = await fixture(t, { evaluator: 'process.exitCode=0;' });
  const result = await f.evaluate(); assert.equal(result.status, 'evaluated'); assert.equal(result.evaluation.eligible, true);
  assert.equal(result.evaluation.improvement.passed, false); assert.equal(await f.target(), 'BAD');
});

for (const change of ['branch', 'plan', 'authority', 'input', 'target', 'head', 'policy']) {
  test(`${change} change before evaluation cannot authorize automatic effects`, opts, async t => {
    const f = await fixture(t); await f.api.propose(f.candidate());
    let api = f.api;
    if (change === 'branch') await f.git('checkout', 'main');
    if (change === 'plan') await f.put('plan.json', JSON.stringify({ ...f.plan, revoked: true }));
    if (change === 'authority') await f.put('authority.md', 'changed authority');
    if (change === 'input') await f.put('check.mjs', 'process.exitCode=0;');
    if (change === 'target') await f.put('target.txt', 'THIRD PARTY');
    if (change === 'head') await f.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-m', 'Concurrent branch development');
    if (change === 'policy') api = await openRSI({ ...f.config, automaticPolicy: { ...f.policy, maxRounds: 2 } });
    await assert.rejects(api.evaluate()); assert.equal(await f.target(), change === 'target' ? 'THIRD PARTY' : 'BAD');
  });
}

test('wrong plan hash, mainline and expired authority are rejected before candidate state exists', opts, async t => {
  const f = await fixture(t);
  const wrong = await openRSI({ ...f.config, automaticPolicy: { ...f.policy, planSha256: '0'.repeat(64) } });
  await assert.rejects(wrong.propose(f.candidate()), { code: 'E_RSI_POLICY' });
  await assert.rejects(openRSI({ ...f.config, automaticPolicy: { ...f.policy, branch: 'main' } }), { code: 'E_RSI_POLICY' });
  await f.put('plan.json', JSON.stringify({ ...f.plan, expiresAt: '2000-01-01T00:00:00.000Z' }));
  await assert.rejects(f.api.propose(f.candidate()), { code: 'E_RSI_AUTHORITY' });
});

test('manual default retains separately authorized adoption and rollback', opts, async t => {
  const f = await fixture(t), api = await openRSI({ ...f.config, automaticPolicy: undefined });
  await api.propose(f.candidate()); assert.equal((await api.evaluate()).next, 'human_approval');
  await assert.rejects(api.adopt(), { code: 'E_RSI_APPROVAL' });
  assert.equal((await api.adopt({ authorize: () => true })).approval.source, 'host-human-approval');
  await assert.rejects(api.rollback(), { code: 'E_RSI_APPROVAL' });
  await api.rollback({ authorize: () => true }); assert.equal(await f.target(), 'BAD');
});

test('explicit observations have a durable finite budget', opts, async t => {
  const f = await fixture(t); await f.evaluate();
  for (let i = 0; i < 3; i++) assert.equal((await f.api.observe()).status, 'adopted');
  await assert.rejects(f.api.observe(), { code: 'E_RSI_OBSERVATION_BUDGET' });
  assert.equal((await f.api.inspect()).postchecks.length, 4);
});

test('rollback restores this round rather than an older adopted baseline', opts, async t => {
  const f = await fixture(t, { metric: true }); await f.evaluate('2'); await f.evaluate('3');
  await f.api.rollback(); assert.equal(await f.target(), '2');
  assert.equal((await f.api.inspect()).automatic.history[0].status, 'adopted');
});

test('a postcheck target mutation is a conflict and never overwritten by automatic rollback', opts, async t => {
  const f = await fixture(t);
  await f.put('check.mjs', `import {readFileSync,writeFileSync} from 'node:fs';const value=readFileSync('target.txt','utf8');if(value!=='GOOD')process.exitCode=3;if(process.cwd()===${JSON.stringify(f.root)}){writeFileSync('target.txt','THIRD PARTY');process.exitCode=7;}`);
  await assert.rejects(f.evaluate(), { code: 'E_RSI_CONFLICT' });
  assert.equal(await f.target(), 'THIRD PARTY');
  const state = JSON.parse(await readFile(join(f.root, 'state/rsi.json'), 'utf8'));
  assert.equal(state.status, 'verifying');
  await assert.rejects(f.api.rollback(), { code: 'E_RSI_RECONCILE' });
});

test('unknown interruption after writing retains reconcile and cannot silently replay', opts, async t => {
  const f = await fixture(t);
  let interrupt = true;
  const api = await openRSI({ ...f.config, protectedPaths: async () => {
    if (interrupt && await f.target() === 'GOOD') throw Object.assign(new Error('simulated host interruption'), { code: 'E_INTERRUPTED' });
    return [];
  } });
  await api.propose(f.candidate()); await assert.rejects(api.evaluate(), { code: 'E_INTERRUPTED' });
  interrupt = false;
  assert.equal(await f.target(), 'GOOD'); assert.equal((await api.inspect()).next, 'reconcile');
  await assert.rejects(api.evaluate()); await assert.rejects(api.rollback(), { code: 'E_RSI_RECONCILE' });
  await assert.rejects(api.propose(f.candidate('OTHER')), { code: 'E_RSI_RECONCILE' });
});

for (const change of ['branch', 'revoked', 'authority']) {
  test(`automatic rollback cannot write after ${change} changes`, opts, async t => {
    const f = await fixture(t); await f.evaluate();
    if (change === 'branch') await f.git('checkout', '-b', 'workflow/unapproved');
    if (change === 'revoked') await f.put('plan.json', JSON.stringify({ ...f.plan, revoked: true }));
    if (change === 'authority') await f.put('authority.md', 'replacement authority');
    await assert.rejects(f.api.rollback()); assert.equal(await f.target(), 'GOOD');
  });
}

test('two rounds that later regress stop even after initially successful postchecks', opts, async t => {
  const f = await fixture(t); await f.evaluate(); await f.put('regression.flag', 'first'); await f.api.observe();
  await rm(join(f.root, 'regression.flag')); await f.evaluate(); await f.put('regression.flag', 'second');
  const result = await f.api.observe(); assert.equal(result.status, 'rolled_back');
  assert.equal(result.automatic.consecutiveFailures, 2); assert.equal(result.automatic.stopReason, 'consecutive_failures');
});

test('damaged automatic adoption cannot recover green without postcheck evidence', opts, async t => {
  const f = await fixture(t); await f.evaluate();
  const path = join(f.root, 'state/rsi.json'), state = JSON.parse(await readFile(path, 'utf8'));
  delete state.postchecks; await writeFile(path, JSON.stringify(state));
  await assert.rejects(f.api.inspect(), /postcheck/);
});

test('metric decrease is measured from finite fixed stdout numbers', opts, async t => {
  const f = await fixture(t, { metric: true, policy: { improvement: { kind: 'metric', name: 'score', direction: 'decrease', minDelta: 1 } } });
  const result = await f.evaluate('0'); assert.equal(result.status, 'adopted'); assert.equal(result.evaluation.improvement.delta, 1);
  assert.ok(result.io.gitCommands <= 32); assert.ok(result.io.filesRead <= 128); assert.ok(result.io.bytesRead <= 8 * 1024 * 1024);
});

test('invalid metric stdout never adopts a successful exit code', opts, async t => {
  const f = await fixture(t, { metric: true, evaluator: 'console.log("unstructured score 2");' });
  const result = await f.evaluate(); assert.equal(result.status, 'evaluated'); assert.equal(result.evaluation.improvement.passed, false); assert.equal(await f.target(), '1');
});

async function hostFixture(t) {
  const f = await fixture(t);
  const { openAgentHost } = await import(process.env.SAGE_AGENT_ADAPTER_DIR ? pathToFileURL(join(process.env.SAGE_AGENT_ADAPTER_DIR, 'agent-host.mjs')) : '../adapters/agent-host.mjs');
  const plan = { version: 1, goal: 'Build the approved project', authority: ['governance.md'], constraints: ['Only approved branch changes'], maxAttempts: 3, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps: [{ id: 'work', objective: 'Implement authorized work', dependsOn: [], scope: ['target.txt'], checks: [], requiresReview: false, admitted: true, humanGate: false }] };
  await f.put('governance.md', 'Fixed project governance distinct from RSI authority.');
  await f.put('continuation.json', JSON.stringify(plan));
  const host = await openAgentHost({ host: 'codex', projectRoot: f.root, planPath: 'continuation.json', statePath: 'state/continuation.json', rsiPlanPath: 'plan.json', rsiStatePath: 'state/rsi.json', rsiAutomaticPolicy: f.policy });
  return { ...f, host, continuationPlan: plan };
}
for (const change of ['authority', 'plan', 'revocation']) {
  test(`automatic host binds distinct continuation ${change} independently of mutable execution state`, opts, async t => {
    const f = await hostFixture(t); await f.host.call('sage_begin', { stepId: 'work', attemptId: 'first' });
    await f.host.call('sage_rsi_propose', f.candidate());
    if (change === 'authority') await f.put('governance.md', 'New authority withdraws prior scope.');
    else await f.put('continuation.json', JSON.stringify({ ...f.continuationPlan, ...(change === 'revocation' ? { revoked: true } : { goal: 'A different project' }) }));
    await assert.rejects(f.host.call('sage_rsi_evaluate'), { code: 'E_RSI_AUTHORITY' });
    assert.equal(await f.target(), 'BAD');
  });
}

test('normal continuation begin and finish do not invalidate a bound automatic proposal', opts, async t => {
  const f = await hostFixture(t); await f.host.call('sage_rsi_propose', f.candidate());
  await f.host.call('sage_begin', { stepId: 'work', attemptId: 'first' });
  await f.host.call('sage_finish', { attemptId: 'first', result: { outcome: 'passed', checks: [] } });
  assert.equal((await f.host.call('sage_rsi_evaluate')).status, 'adopted'); assert.equal(await f.target(), 'GOOD');
});

test('continuation plan is bound even when no execution state exists yet', opts, async t => {
  const f = await hostFixture(t); await f.host.call('sage_rsi_propose', f.candidate());
  await f.put('continuation.json', JSON.stringify({ ...f.continuationPlan, goal: 'Different scope before any execution' }));
  await assert.rejects(f.host.call('sage_rsi_evaluate'), { code: 'E_RSI_STALE' }); assert.equal(await f.target(), 'BAD');
});

test('an already revoked continuation plan cannot seed automatic RSI', opts, async t => {
  const f = await hostFixture(t); await f.put('continuation.json', JSON.stringify({ ...f.continuationPlan, revoked: true }));
  await assert.rejects(f.host.call('sage_rsi_propose', f.candidate()), { code: 'E_RSI_AUTHORITY' });
});

test('metric policy requires an explicit string metric name', opts, async t => {
  const f = await fixture(t);
  await assert.rejects(openRSI({ ...f.config, automaticPolicy: { ...f.policy, improvement: { kind: 'metric', direction: 'increase', minDelta: 1 } } }), { code: 'E_RSI_POLICY' });
});
