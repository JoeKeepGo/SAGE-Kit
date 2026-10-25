import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';
import { createDshRuntime, dshAvailable, dshSkipReason, toolResults, toolResultText } from './helpers/dsh-runtime.mjs';

const skip = !dshAvailable ? dshSkipReason : process.platform === 'win32' ? 'RSI command-tree termination is not verified on Windows; evaluation is deliberately unavailable.' : false;
const options = { skip, timeout: 20000 };
const original = 'old policy\n', candidate = 'new policy\n';
const call = (tool, args = {}) => ({ tool, args });
const propose = () => call('sage_rsi_propose', {
  hypothesis: 'Replacing the policy fixes the recorded evaluation failure.',
  feedback: JSON.stringify([{ path: 'feedback.txt', kind: 'failure' }]),
  files: JSON.stringify([{ path: 'policy.txt', content: candidate }]),
});

async function fixture(t, { approvalPolicy = 'ask', withApproval = true } = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-dsh-rsi-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = (path, content) => writeFile(join(root, path), content);
  await put('governance.md', 'Preserve project authority and only change the explicitly approved RSI candidate.\n');
  await put('rsi-authority.md', 'Do not change assessment assets or expand the allowed candidate targets.\n');
  await put('feedback.txt', 'Observed failure: the policy check rejected the old policy.\n');
  await put('policy.txt', original);
  await put('check.mjs', "import{readFileSync}from'node:fs';const actual=readFileSync('policy.txt','utf8');console.log(actual==='new policy\\n'?'policy check passed':'policy check failed');process.exit(actual==='new policy\\n'?0:1);\n");
  await put('continuation-plan.json', JSON.stringify({ version: 1, goal: 'Improve a fixture policy through governed RSI', authority: ['governance.md'], constraints: ['No network', 'No automatic adoption'], maxAttempts: 3, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps: [{ id: 'work', objective: 'Inspect controlled improvement evidence', dependsOn: [], scope: ['policy.txt'], checks: ['check'], requiresReview: false, admitted: true, humanGate: false }] }));
  await put('rsi-plan.json', JSON.stringify({ version: 1, authority: ['rsi-authority.md'], inputs: ['policy.txt', 'check.mjs'], targets: ['policy.txt'], command: [process.execPath, 'check.mjs'], expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, maxEvaluations: 2, timeoutMs: 2000, maxOutputBytes: 4096 }));
  const config = { projectRoot: root, planPath: 'continuation-plan.json', statePath: 'continuation-state.json', rsiPlanPath: 'rsi-plan.json', rsiStatePath: 'rsi-state.json', guardedTools: [] };
  const runtime = await createDshRuntime(t, config, withApproval ? { approvalPolicy } : {});
  const agent = await runtime.createAgent();
  return { root, put, runtime, agent, policy: () => readFile(join(root, 'policy.txt'), 'utf8') };
}
function success(run) {
  assert.deepEqual(run.errors, []);
  assert.equal(run.unusedActions, 0);
  assert.equal(run.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
}
const parsed = result => JSON.parse(toolResultText(result));
const asked = run => run.events.filter(event => event.type === 'approval/asked');
const decided = run => run.events.filter(event => event.type === 'approval/decided');

async function evaluated(f) {
  const run = await f.runtime.run(f.agent, [propose(), call('sage_rsi_evaluate')]);
  success(run);
  for (const result of toolResults(run)) assert.notEqual(result.message.isError, true, toolResultText(result));
  const value = parsed(toolResults(run).at(-1));
  assert.equal(value.evaluation.eligible, true);
  assert.equal(await f.policy(), original, 'evaluation must not modify the real target');
  return value;
}

test('DSH RSI native approval binds candidate/evaluation, adopts once and separately approves rollback', options, async t => {
  const f = await fixture(t);
  const value = await evaluated(f);
  const approvals = [];
  f.runtime.ctx.on('approval/request', async request => {
    approvals.push({ toolName: request.toolName, callId: request.callId, reason: request.reason });
    assert.match(request.reason, /policy\.txt/);
    assert.ok(request.reason.includes(value.proposal.digest), 'approval must identify the exact candidate');
    if (request.toolName === 'sage_rsi_adopt') {
      assert.equal(await f.policy(), original);
      assert.ok(request.reason.includes(value.evaluation.digest), 'adoption must identify the exact evaluation');
      // Human interaction must not inherit the two-second governance read timer.
      await delay(2100);
    } else assert.equal(await f.policy(), candidate);
    return 'allowed-once';
  });
  const run = await f.runtime.run(f.agent, [
    call('sage_rsi_adopt'),
    async () => { assert.equal(await f.policy(), candidate); return call('sage_rsi_rollback'); },
  ]);
  success(run);
  for (const result of toolResults(run)) assert.notEqual(result.message.isError, true, toolResultText(result));
  assert.equal(await f.policy(), original);
  assert.deepEqual(approvals.map(item => item.toolName), ['sage_rsi_adopt', 'sage_rsi_rollback']);
  assert.equal(new Set(approvals.map(item => item.callId)).size, 2);
  assert.equal(asked(run).length, 2);
  assert.deepEqual(decided(run).map(event => event.data.outcome), ['allowed-once', 'allowed-once']);
  for (const request of asked(run)) {
    assert.ok(decided(run).some(event => event.data.id === request.data.id));
    assert.ok(request.seq > run.events.find(event => event.type === 'turn/start').seq);
    assert.ok(request.seq < run.events.findLast(event => event.type === 'turn/end').seq);
  }
  const schemas = run.requests[0].tools.filter(tool => tool.name.startsWith('sage_rsi_'));
  assert.equal(schemas.length, 6);
  for (const schema of schemas) assert.equal(Object.hasOwn(schema.parameters.properties, 'approved'), false);
});

for (const mode of ['missing-service', 'missing-answerer', 'rejected', 'cancelled', 'unavailable', 'invalid-boolean', 'never']) {
  test(`DSH RSI ${mode} cannot authorize adoption even with a global tool allow`, options, async t => {
    const f = await fixture(t, { withApproval: mode !== 'missing-service', approvalPolicy: mode === 'never' ? 'never' : 'ask' });
    await evaluated(f);
    let answered = 0;
    if (!['missing-service', 'missing-answerer'].includes(mode)) f.runtime.ctx.on('approval/request', () => {
      answered++;
      return mode === 'invalid-boolean' ? true : mode === 'never' ? 'allowed-once' : mode;
    });
    f.runtime.ctx.on('tools/pre-execute', () => ({ kind: 'allow' }));
    const run = await f.runtime.run(f.agent, [call('sage_rsi_adopt')]);
    success(run);
    assert.equal(toolResults(run)[0].message.isError, true);
    assert.equal(await f.policy(), original);
    assert.equal(asked(run).length, mode === 'missing-service' ? 0 : 1);
    if (mode === 'never') assert.equal(answered, 0);
    if (mode !== 'missing-service') assert.notEqual(decided(run)[0].data.outcome, 'allowed-once');
  });
}

test('DSH RSI approval waiting target change invalidates the exact approved candidate', options, async t => {
  const f = await fixture(t);
  await evaluated(f);
  f.runtime.ctx.on('approval/request', async () => {
    await f.put('policy.txt', 'third-party edit during approval\n');
    return 'allowed-once';
  });
  const run = await f.runtime.run(f.agent, [call('sage_rsi_adopt')]);
  success(run);
  assert.equal(decided(run)[0].data.outcome, 'allowed-once');
  assert.equal(toolResults(run)[0].message.isError, true);
  assert.equal(await f.policy(), 'third-party edit during approval\n');
});

test('DSH RSI actual session cancellation during native approval leaves policy unchanged', options, async t => {
  const f = await fixture(t);
  await evaluated(f);
  f.runtime.ctx.on('approval/request', request => new Promise(resolve => {
    request.signal.addEventListener('abort', () => resolve('cancelled'), { once: true });
    request.agent.cancel({ kind: 'user' });
  }));
  const run = await f.runtime.run(f.agent, [call('sage_rsi_adopt')]);
  assert.equal(await f.policy(), original);
  assert.equal(asked(run).length, 1);
  assert.equal(decided(run)[0].data.outcome, 'cancelled');
  assert.notEqual(run.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
});

for (const path of ['continuation-plan.json', 'continuation-state.json', 'governance.md']) {
  test(`DSH RSI rejects a plan that names protected continuation asset ${path} as a candidate target`, options, async t => {
    const f = await fixture(t);
    const plan = JSON.parse(await readFile(join(f.root, 'rsi-plan.json'), 'utf8'));
    plan.inputs = [path, 'check.mjs'];
    plan.targets = [path];
    await f.put('rsi-plan.json', JSON.stringify(plan));
    const run = await f.runtime.run(f.agent, [call('sage_rsi_propose', {
      hypothesis: 'This forbidden candidate must never replace governance.',
      feedback: JSON.stringify([{ path: 'feedback.txt', kind: 'failure' }]),
      files: JSON.stringify([{ path, content: 'unauthorized replacement' }]),
    })]);
    success(run);
    assert.equal(toolResults(run)[0].message.isError, true);
    await assert.rejects(readFile(join(f.root, 'rsi-state.json')), { code: 'ENOENT' });
    assert.equal(await f.policy(), original);
  });
}

test('DSH RSI rechecks newly mapped governance authority after waiting for approval', options, async t => {
  const f = await fixture(t);
  await evaluated(f);
  f.runtime.ctx.on('approval/request', async () => {
    await f.put('additional-authority.md', 'New explicit authority while the approval was pending.\n');
    const plan = JSON.parse(await readFile(join(f.root, 'continuation-plan.json'), 'utf8'));
    plan.authority.push('additional-authority.md');
    await f.put('continuation-plan.json', JSON.stringify(plan));
    return 'allowed-once';
  });
  const run = await f.runtime.run(f.agent, [call('sage_rsi_adopt')]);
  assert.equal(decided(run)[0].data.outcome, 'allowed-once');
  assert.equal(toolResults(run)[0].message.isError, true);
  assert.equal(await f.policy(), original);
});
