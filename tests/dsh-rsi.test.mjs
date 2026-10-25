import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
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

async function fixture(t, { approvalPolicy = 'ask', withApproval = true, automatic = false, postFailure = false, improvement = { kind: 'repair' } } = {}) {
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
  if (automatic) {
    await put('governance.md', 'Only the fixed development branch policy may authorize automatic RSI; final acceptance stays human.');
    const plan = JSON.parse(await readFile(join(root, 'continuation-plan.json'), 'utf8'));
    plan.constraints = ['No network', 'Automatic RSI only under the fixed branch policy'];
    await put('continuation-plan.json', JSON.stringify(plan));
    const marker = join(root, 'regression.flag');
    await put('check.mjs', `import{readFileSync,existsSync}from'node:fs';const good=readFileSync('policy.txt','utf8')==='new policy\\n';process.exitCode=good&&!existsSync(${JSON.stringify(marker)})&&!(${postFailure}&&process.cwd()===${JSON.stringify(root)})?0:1;`);
    if (improvement.kind === 'metric') await put('check.mjs', "import{readFileSync}from'node:fs';console.log(JSON.stringify({metrics:{score:readFileSync('policy.txt','utf8')==='new policy\\n'?2:1}}));");
    let baseline, failure;
    try { baseline = await promisify(execFile)(process.execPath, ['check.mjs'], { cwd: root, timeout: 3000, maxBuffer: 4096 }); }
    catch (cause) { failure = cause; }
    if (improvement.kind === 'repair') assert.equal(failure?.code, 1, 'record a real failing baseline before proposing');
    else assert.equal(JSON.parse(baseline.stdout).metrics.score, 1);
    await put('feedback.txt', improvement.kind === 'repair' ? 'Fixed original check exit 1.\n' + (failure.stdout ?? '') + (failure.stderr ?? '') : 'Observed original score: ' + baseline.stdout);
    config.rsiAutomaticPolicy = { branch: 'workflow/auto-fixture', baseBranch: 'main', planSha256: createHash('sha256').update(await readFile(join(root, 'rsi-plan.json'))).digest('hex'), maxRounds: 2, improvement };
    await put('cordis.patch.yml', JSON.stringify({ config }));
    await put('.gitignore', 'continuation-state.json*\nrsi-state.json*\nregression.flag\n');
    const git = args => promisify(execFile)('git', args, { cwd: root, env: { PATH: '/usr/bin:/bin', HOME: root, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' }, timeout: 3000, maxBuffer: 65536 });
    await git(['init', '-b', 'main']); await git(['add', '.']);
    await git(['-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid', '-c', 'core.hooksPath=/dev/null', 'commit', '--no-gpg-sign', '-m', 'Isolated acceptance baseline']);
    await git(['checkout', '-b', 'workflow/auto-fixture']);
  }
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

for (const path of ['continuation-plan.json', 'continuation-state.json', 'governance.md', 'AGENTS.md', 'cordis.patch.yml']) {
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


for (const postFailure of [false, true]) {
  test(`DSH automatic RSI without approval service ${postFailure ? 'rolls back a failed actual postcheck' : 'adopts then rolls back an observed regression'}`, options, async t => {
    const f = await fixture(t, { automatic: true, withApproval: false, postFailure });
    assert.equal(f.runtime.ctx.get('approval'), undefined);
    const run = await f.runtime.run(f.agent, [propose(), call('sage_rsi_evaluate')]);
    success(run);
    for (const result of toolResults(run)) assert.notEqual(result.message.isError, true, toolResultText(result));
    const schemas = run.requests[0].tools.filter(tool => tool.name.startsWith('sage_rsi_'));
    assert.equal(schemas.length, 6);
    assert.ok(schemas.some(tool => tool.name === 'sage_rsi_observe'));
    assert.ok(!schemas.some(tool => tool.name === 'sage_rsi_adopt'));
    assert.match(schemas.find(tool => tool.name === 'sage_rsi_evaluate').description, /preauthorized/);
    assert.match(JSON.stringify(run.requests[0].messages), /preauthorized/);
    assert.equal(asked(run).length, 0);
    assert.equal(parsed(toolResults(run).at(-1)).status, postFailure ? 'rolled_back' : 'adopted');
    assert.equal(await f.policy(), postFailure ? original : candidate);
    if (!postFailure) {
      await f.put('regression.flag', 'Observed external regression');
      const observed = await f.runtime.run(f.agent, [call('sage_rsi_observe')]);
      success(observed);
      assert.notEqual(toolResults(observed)[0].message.isError, true, toolResultText(toolResults(observed)[0]));
      assert.equal(parsed(toolResults(observed)[0]).status, 'rolled_back');
      assert.equal(asked(observed).length, 0);
      assert.equal(await f.policy(), original);
    }
    t.diagnostic('Real DSH components, deterministic local model, real Git fixture and fixed commands; no approval service or model/network call.');
  });
}


test('DSH automatic metric configuration reaches the core and adopts a measured improvement', options, async t => {
  const f = await fixture(t, { automatic: true, withApproval: false, improvement: { kind: 'metric', name: 'score', direction: 'increase', minDelta: 1 } });
  const run = await f.runtime.run(f.agent, [call('sage_rsi_propose', {
    hypothesis: 'Raise the fixed score from one to two', feedback: JSON.stringify([{ path: 'feedback.txt', kind: 'rework' }]),
    files: JSON.stringify([{ path: 'policy.txt', content: candidate }]),
  }), call('sage_rsi_evaluate')]);
  success(run);
  for (const result of toolResults(run)) assert.notEqual(result.message.isError, true, toolResultText(result));
  assert.equal(parsed(toolResults(run).at(-1)).status, 'adopted');
  assert.equal(await f.policy(), candidate);
  assert.equal(asked(run).length, 0);
});

for (const change of ['authority', 'revocation']) {
  test(`DSH automatic RSI refuses distinct continuation ${change} changes after proposal`, options, async t => {
    const f = await fixture(t, { automatic: true, withApproval: false });
    const run = await f.runtime.run(f.agent, [call('sage_begin', { stepId: 'work', attemptId: 'authority-binding' }), propose(), async () => {
      if (change === 'authority') await f.put('governance.md', 'Changed project authority withdraws the prior scope.');
      else {
        const plan = JSON.parse(await readFile(join(f.root, 'continuation-plan.json'), 'utf8'));
        await f.put('continuation-plan.json', JSON.stringify({ ...plan, revoked: true }));
      }
      return call('sage_rsi_evaluate');
    }]);
    assert.deepEqual(run.errors, []);
    // Native governance refresh rejects the changed authority before this tool executes.
    assert.equal(run.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'blocked');
    assert.equal(JSON.parse(await readFile(join(f.root, 'rsi-state.json'), 'utf8')).status, 'proposed');
    assert.equal(await f.policy(), original); assert.equal(asked(run).length, 0);
  });
}
