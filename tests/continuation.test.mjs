import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm, symlink, stat, utimes } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { tmpdir, platform, release, arch } from 'node:os';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { openContinuation } from '../adapters/continuation.mjs';

const execute = promisify(execFile);
const moduleUrl = new URL('../adapters/continuation.mjs', import.meta.url).href;
const layouts = [
  { planPath: 'governance/plan.json', statePath: 'observations/state.json', authority: 'docs/rules.md' },
  { planPath: 'planning/current/execution.json', statePath: 'local/progress/attempts.json', authority: 'policy/current/spec.txt' },
];

function step(id, overrides = {}) {
  return { id, objective: `Produce ${id}`, dependsOn: [], scope: ['output'], checks: ['test'], requiresReview: false, admitted: true, humanGate: false, ...overrides };
}

async function fixture(t, options = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-continuation-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const layout = options.layout ?? layouts[0];
  const config = { root, planPath: layout.planPath, statePath: layout.statePath };
  const put = async (path, content) => {
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), content);
    return path;
  };
  await put(layout.authority, 'Project authority: preserve user work; run required checks.\n');
  const plan = {
    version: 1, goal: 'Complete the approved local work', authority: [layout.authority],
    constraints: ['Preserve user work', 'No network or publication'], maxAttempts: 10,
    expiresAt: '2099-01-01T00:00:00.000Z', revoked: false,
    steps: [step('first')], ...options.plan,
  };
  await put(config.planPath, JSON.stringify(plan));
  await mkdir(dirname(join(root, config.statePath)), { recursive: true });
  const controller = await openContinuation(config);
  const pass = async (id, review = false) => {
    const evidence = await put(`output/${id}.check`, 'check passed\n');
    return { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence }],
      ...(review ? { review: await put(`output/${id}.review`, 'independent review fixture\n') } : {}) };
  };
  return { root, config, plan, layout, controller, put, pass };
}

for (const layout of layouts) {
  test(`three real local commands continue under explicit layout ${layout.planPath}`, async (t) => {
    const f = await fixture(t, { layout, plan: { steps: [step('first'), step('second', { dependsOn: ['first'], requiresReview: true }), step('third', { dependsOn: ['second'] })] } });
    const authorityBefore = await readFile(join(f.root, layout.authority), 'utf8');
    for (const id of ['first', 'second', 'third']) {
      const next = await f.controller.inspect();
      assert.equal(next.action, 'continue');
      assert.equal(next.step.id, id);
      const context = JSON.stringify(next.context);
      for (const text of [f.plan.goal, ...f.plan.constraints, layout.authority, 'output', 'test']) assert.ok(context.includes(text), `context must retain ${text}`);
      const started = await f.controller.begin(id, `attempt-${id}`);
      assert.equal(started.replayed, false);
      await mkdir(join(f.root, 'output'), { recursive: true });
      const script = `const fs=require('node:fs');const id=process.argv[1];fs.writeFileSync('output/'+id+'.txt',id);fs.writeFileSync('output/'+id+'.check',fs.readFileSync('output/'+id+'.txt','utf8')===id?'passed':'failed');`;
      await execute(process.execPath, ['-e', script, id], { cwd: f.root, timeout: 5000 });
      assert.equal(await readFile(join(f.root, `output/${id}.check`), 'utf8'), 'passed');
      const result = { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: `output/${id}.check` }] };
      if (id === 'second') result.review = await f.put('output/second.review', 'Reviewed command and result.\n');
      await f.controller.finish(`attempt-${id}`, result);
    }
    assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
    assert.equal(await readFile(join(f.root, layout.authority), 'utf8'), authorityBefore);
  });
}

test('failed command can be repaired once without mandatory Light review', async (t) => {
  const f = await fixture(t);
  await f.controller.begin('first', 'failed-attempt');
  await assert.rejects(execute(process.execPath, ['-e', 'process.exit(7)'], { cwd: f.root, timeout: 5000 }));
  await f.controller.finish('failed-attempt', { outcome: 'failed', checks: [] });
  assert.equal((await f.controller.inspect()).action, 'continue');
  await f.controller.begin('first', 'repaired-attempt');
  await f.controller.finish('repaired-attempt', await f.pass('repaired'));
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
});

test('two failures require reassessment and forbid another attempt', async (t) => {
  const f = await fixture(t);
  for (const id of ['failure-one', 'failure-two']) {
    await f.controller.begin('first', id);
    await f.controller.finish(id, { outcome: 'failed', checks: [] });
  }
  assert.equal((await f.controller.inspect()).action, 'reassess');
  await assert.rejects(f.controller.begin('first', 'failure-three'));
});

test('not_executed never satisfies a dependency', async (t) => {
  const f = await fixture(t, { plan: { steps: [step('first'), step('second', { dependsOn: ['first'] })] } });
  await f.controller.begin('first', 'not-executed');
  await f.controller.finish('not-executed', { outcome: 'not_executed', checks: [] });
  assert.notEqual((await f.controller.inspect()).step?.id, 'second');
  await assert.rejects(f.controller.begin('second', 'premature'));
});

test('SIGKILL after a real side effect requires reconciliation, never another execution', { timeout: 15000 }, async (t) => {
  const f = await fixture(t);
  const childSource = `import {openContinuation} from ${JSON.stringify(moduleUrl)};
    import {appendFile} from 'node:fs/promises';
    const c=await openContinuation(JSON.parse(process.argv[2]));
    const started=await c.begin('first','crash-attempt');
    if(!started.replayed) await appendFile(process.argv[3],'performed\\n');
    setInterval(()=>{},1000);`;
  const sideEffect = join(f.root, 'side-effect.txt');
  const childFile = await f.put('crash-host.mjs', childSource);
  // This is an ordinary host process, not a nested node:test worker. Do not
  // inherit the parent's test-runner protocol. Observe the actual file effect
  // because sandbox process transports may suppress child stdout and IPC.
  const childEnv = { ...process.env };
  delete childEnv.NODE_TEST_CONTEXT;
  const child = spawn(process.execPath, [join(f.root, childFile), JSON.stringify(f.config), sideEffect], {
    env: childEnv, stdio: ['ignore', 'ignore', 'pipe'],
  });
  t.after(() => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL'); });
  let stderr = '';
  let spawnError;
  child.once('error', (error) => { spawnError = error; });
  child.stderr.on('data', (data) => { stderr += data; });
  const closed = new Promise((resolve) => child.once('close', (code, signal) => resolve({ code, signal })));
  const deadline = Date.now() + 7000;
  while (true) {
    if (spawnError) throw spawnError;
    try {
      if (await readFile(sideEffect, 'utf8') === 'performed\n') break;
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`Premature child exit ${child.exitCode}/${child.signalCode}: ${stderr}`);
    }
    if (Date.now() >= deadline) throw new Error(`Child never reached side effect (pid=${child.pid}): ${stderr}`);
    await delay(20);
  }
  assert.equal(child.kill('SIGKILL'), true);
  const exit = await closed;
  if (process.platform !== 'win32') assert.equal(exit.signal, 'SIGKILL');
  const resumed = await openContinuation(f.config);
  assert.equal((await resumed.inspect()).action, 'reconcile');
  await assert.rejects(resumed.begin('first', 'different-attempt'));
  assert.equal((await resumed.begin('first', 'crash-attempt')).replayed, true);
  assert.equal(await readFile(sideEffect, 'utf8'), 'performed\n');
  await resumed.finish('crash-attempt', await f.pass('reconciled'));
  assert.equal((await resumed.inspect()).action, 'complete_pending_acceptance');
});

test('passed requires every check, successful checks, existing evidence and required review', async (t) => {
  const f = await fixture(t, { plan: { steps: [step('first', { requiresReview: true })] } });
  await f.controller.begin('first', 'review-attempt');
  const valid = await f.pass('reviewed', true);
  for (const invalid of [
    { ...valid, checks: [] },
    { ...valid, checks: [{ ...valid.checks[0], passed: false }] },
    { ...valid, checks: [{ ...valid.checks[0], evidence: 'output/missing' }] },
    { outcome: 'passed', checks: valid.checks },
    { ...valid, review: 'output/missing-review' },
  ]) {
    await assert.rejects(f.controller.finish('review-attempt', invalid));
    assert.equal((await f.controller.inspect()).action, 'reconcile');
  }
  await f.controller.finish('review-attempt', valid);
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
});

for (const [name, plan, action] of [
  ['not admitted', { steps: [step('first', { admitted: false })] }, 'blocked'],
  ['human approval', { steps: [step('first', { humanGate: true })] }, 'human_gate'],
  ['revoked', { revoked: true }, 'revoked'],
  ['expired', { expiresAt: '2000-01-01T00:00:00.000Z' }, 'expired'],
]) {
  test(`${name} stops admission`, async (t) => {
    const f = await fixture(t, { plan });
    assert.equal((await f.controller.inspect()).action, action);
    await assert.rejects(f.controller.begin('first', 'forbidden'));
  });
}

test('budget exhaustion stops retries', async (t) => {
  const f = await fixture(t, { plan: { maxAttempts: 1 } });
  await f.controller.begin('first', 'only-attempt');
  await f.controller.finish('only-attempt', { outcome: 'failed', checks: [] });
  assert.equal((await f.controller.inspect()).action, 'budget_exhausted');
  await assert.rejects(f.controller.begin('first', 'over-budget'));
});

test('independent admitted step can advance past an unadmitted dependency chain', async (t) => {
  const f = await fixture(t, { plan: { steps: [step('first', { admitted: false }), step('second', { dependsOn: ['first'] }), step('independent')] } });
  assert.equal((await f.controller.inspect()).step.id, 'independent');
  await f.controller.begin('independent', 'independent-attempt');
  await f.controller.finish('independent-attempt', await f.pass('independent'));
  assert.equal((await f.controller.inspect()).action, 'blocked');
});

for (const kind of ['authority', 'plan']) {
  test(`${kind} content change invalidates the bound round`, async (t) => {
    const f = await fixture(t, { plan: { steps: [step('first'), step('second', { dependsOn: ['first'] })] } });
    await f.controller.begin('first', 'bound-attempt');
    await f.controller.finish('bound-attempt', await f.pass('bound'));
    if (kind === 'authority') await f.put(f.layout.authority, 'Changed project authority\n');
    else await f.put(f.config.planPath, JSON.stringify({ ...f.plan, constraints: ['New constraint'] }));
    const resumed = await openContinuation(f.config);
    assert.equal((await resumed.inspect()).action, 'authority_changed');
    await assert.rejects(resumed.begin('second', 'changed-attempt'));
  });
}

for (const change of ['edit', 'delete', 'review']) {
  test(`${change} of passed evidence blocks downstream admission`, async (t) => {
    const f = await fixture(t, { plan: { steps: [step('first', { requiresReview: true }), step('second', { dependsOn: ['first'] })] } });
    await f.controller.begin('first', 'evidence-attempt');
    const result = await f.pass('evidence', true);
    await f.controller.finish('evidence-attempt', result);
    if (change === 'delete') await rm(join(f.root, result.checks[0].evidence));
    else await f.put(change === 'review' ? result.review : result.checks[0].evidence, 'changed content');
    assert.equal((await f.controller.inspect()).action, 'evidence_changed');
    await assert.rejects(f.controller.begin('second', 'invalid-evidence'));
  });
}

test('attempt keys and results are idempotent but conflicting results are rejected', async (t) => {
  const f = await fixture(t);
  const first = await f.controller.begin('first', 'same-key');
  const replay = await f.controller.begin('first', 'same-key');
  assert.equal(first.replayed, false);
  assert.equal(replay.replayed, true);
  assert.deepEqual(replay.attempt, first.attempt);
  await assert.rejects(f.controller.begin('first', 'different-key'));
  const result = await f.pass('idempotent');
  const finished = await f.controller.finish('same-key', result);
  assert.deepEqual(await f.controller.finish('same-key', result), finished);
  await assert.rejects(f.controller.finish('same-key', { outcome: 'failed', checks: [] }));
});

for (const content of ['', 'not-json']) {
  test(`${content ? 'corrupt' : 'empty'} lock is never automatically taken over`, async (t) => {
    const f = await fixture(t);
    const lock = `${f.config.statePath}.lock`;
    await f.put(lock, content);
    await assert.rejects(f.controller.begin('first', 'locked-attempt'));
    assert.equal(await readFile(join(f.root, lock), 'utf8'), content);
  });
}

test('corrupt persistent state is rejected, never initialized over', async (t) => {
  const f = await fixture(t);
  await f.put(f.config.statePath, '{broken');
  await assert.rejects(async () => { const c = await openContinuation(f.config); await c.inspect(); });
  assert.equal(await readFile(join(f.root, f.config.statePath), 'utf8'), '{broken');
});

for (const [name, steps] of [
  ['duplicate ids', [step('first'), step('first')]],
  ['missing dependency', [step('first', { dependsOn: ['missing'] })]],
  ['duplicate dependency', [step('first'), step('second', { dependsOn: ['first', 'first'] })]],
  ['dependency cycle', [step('first', { dependsOn: ['second'] }), step('second', { dependsOn: ['first'] })]],
  ['escaping scope', [step('first', { scope: ['../outside'] })]],
]) {
  test(`reject ${name}`, async (t) => {
    await assert.rejects(async () => { const f = await fixture(t, { plan: { steps } }); await f.controller.inspect(); });
  });
}

test('symlink authority is rejected', async (t) => {
  const f = await fixture(t);
  await f.put('actual-authority.md', 'same project, symlink still forbidden');
  await rm(join(f.root, f.layout.authority));
  await symlink(join(f.root, 'actual-authority.md'), join(f.root, f.layout.authority));
  await assert.rejects(async () => { const c = await openContinuation(f.config); await c.inspect(); });
});

test('unsafe plan/state paths are rejected without accessing outside the project', async (t) => {
  const f = await fixture(t);
  for (const override of [{ planPath: '../outside.json' }, { statePath: '../outside.json' }, { statePath: '/tmp/outside.json' }]) {
    await assert.rejects(async () => { const c = await openContinuation({ ...f.config, ...override }); await c.inspect(); });
  }
});

test('oversized governance input is rejected rather than silently truncated', async (t) => {
  const f = await fixture(t);
  await f.put(f.layout.authority, 'x'.repeat(2 * 1024 * 1024));
  await assert.rejects(f.controller.inspect());
});

test('attempt key cannot be reused for a different step', async (t) => {
  const f = await fixture(t, { plan: { steps: [step('first'), step('second', { dependsOn: ['first'] })] } });
  await f.controller.begin('first', 'shared-key');
  await f.controller.finish('shared-key', await f.pass('first'));
  await assert.rejects(f.controller.begin('second', 'shared-key'));
  assert.equal((await f.controller.inspect()).step.id, 'second');
});

for (const damage of ['missing digest', 'extra digest', 'missing required check', 'missing required review']) {
  test(`persisted passed attempt rejects ${damage} during recovery`, async (t) => {
    const f = await fixture(t, { plan: { steps: [step('first', { requiresReview: true }), step('second', { dependsOn: ['first'] })] } });
    await f.controller.begin('first', 'corrupted-attempt');
    const result = await f.pass('persisted', true);
    await f.controller.finish('corrupted-attempt', result);
    const state = JSON.parse(await readFile(join(f.root, f.config.statePath), 'utf8'));
    const attempt = state.attempts[0];
    if (damage === 'missing digest') {
      attempt.evidence = [];
      // Reproduce the original escape: removed proofs must not stop detection
      // of a deleted evidence file merely because the digest list is empty.
      await rm(join(f.root, result.checks[0].evidence));
    } else if (damage === 'extra digest') {
      const path = await f.put('output/unrelated.check', 'unrelated proof');
      attempt.evidence.push({ path, sha256: createHash('sha256').update('unrelated proof').digest('hex') });
    } else if (damage === 'missing required check') {
      attempt.result.checks = [];
      attempt.evidence = attempt.evidence.filter(e => e.path === attempt.result.review);
    } else {
      const oldReview = attempt.result.review;
      delete attempt.result.review;
      attempt.evidence = attempt.evidence.filter(e => e.path !== oldReview);
    }
    // Keep the result checksum consistent so the test exercises semantic
    // validation and proof completeness, not a trivial checksum mismatch.
    attempt.resultKey = createHash('sha256').update(JSON.stringify(attempt.result)).digest('hex');
    const corrupted = JSON.stringify(state);
    await f.put(f.config.statePath, corrupted);
    const resumed = await openContinuation(f.config);
    await assert.rejects(resumed.inspect());
    await assert.rejects(resumed.begin('second', 'cannot-advance'));
    assert.equal(await readFile(join(f.root, f.config.statePath), 'utf8'), corrupted);
  });
}

test('resource accounting reads a shared proof only once across passed steps and review references', async (t) => {
  const f = await fixture(t, { plan: { steps: [
    step('first', { requiresReview: true }),
    step('second', { dependsOn: ['first'], requiresReview: true }),
    step('third', { dependsOn: ['second'], requiresReview: true }),
  ] } });
  const proof = await f.put('output/shared-proof.txt', 'Shared fixture check and review evidence.\n');
  const result = { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: proof }], review: proof };
  for (const id of ['first', 'second', 'third']) {
    await f.controller.begin(id, `resource-${id}`);
    await f.controller.finish(`resource-${id}`, result);
    const inspected = await f.controller.inspect();
    const uniqueInputs = [f.config.planPath, f.layout.authority, f.config.statePath, proof];
    const sizes = await Promise.all(uniqueInputs.map(path => stat(join(f.root, path))));
    assert.deepEqual(inspected.io, { filesRead: 4, bytesRead: sizes.reduce((sum, item) => sum + item.size, 0) });
  }
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
});

test('resource budget rejects aggregate authority bytes even when every individual file is legal', async (t) => {
  const authority = Array.from({ length: 9 }, (_, index) => `authority/rule-${index}.txt`);
  const f = await fixture(t, { plan: { authority } });
  const legalSizeContent = 'x'.repeat(1024 * 1024);
  for (const path of authority) await f.put(path, legalSizeContent);
  await assert.rejects(f.controller.inspect(), { code: 'E_READ_BUDGET' });
  await assert.rejects(f.controller.begin('first', 'too-many-bytes'), { code: 'E_READ_BUDGET' });
  await assert.rejects(stat(join(f.root, f.config.statePath)), { code: 'ENOENT' });
});

test('resource budget accepts 128 distinct inputs but rejects the 129th evidence file', async (t) => {
  const authority = Array.from({ length: 100 }, (_, index) => `authority/rule-${index}.txt`);
  const checkNames = Array.from({ length: 26 }, (_, index) => `check-${index}`);
  const f = await fixture(t, { plan: { authority, steps: [
    step('first', { checks: checkNames }), step('second', { dependsOn: ['first'] }),
    step('third', { dependsOn: ['second'] }),
  ] } });
  for (const path of authority) await f.put(path, 'Approved project rule.\n');
  const checks = [];
  for (const id of checkNames) checks.push({ id, passed: true, evidence: await f.put(`output/${id}.txt`, 'pass\n') });
  await f.controller.begin('first', 'many-inputs-first');
  await f.controller.finish('many-inputs-first', { outcome: 'passed', checks });
  // plan + state + 100 authorities + 26 proofs = 128 distinct content reads.
  const boundary = await f.controller.inspect();
  assert.equal(boundary.action, 'continue');
  assert.equal(boundary.io.filesRead, 128);
  await f.controller.begin('second', 'many-inputs-second');
  await f.controller.finish('many-inputs-second', await f.pass('one-more-proof'));
  await assert.rejects(f.controller.inspect(), { code: 'E_READ_BUDGET' });
  await assert.rejects(f.controller.begin('third', 'over-file-budget'), { code: 'E_READ_BUDGET' });
});

for (const kind of ['authority', 'evidence']) {
  test(`resource optimization never trusts unchanged size and mtime for ${kind}`, async (t) => {
    const f = await fixture(t, { plan: { steps: [step('first'), step('second', { dependsOn: ['first'] })] } });
    const evidence = await f.put('output/fixed-size-proof.txt', 'proof-A');
    if (kind === 'authority') await f.put(f.layout.authority, 'rule--A');
    const target = join(f.root, kind === 'authority' ? f.layout.authority : evidence);
    const fixedTime = new Date('2000-01-01T00:00:00.000Z');
    await utimes(target, fixedTime, fixedTime);
    await f.controller.begin('first', `same-metadata-${kind}`);
    await f.controller.finish(`same-metadata-${kind}`, { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence }] });
    assert.equal((await f.controller.inspect()).action, 'continue');
    const before = await stat(target);
    await writeFile(target, kind === 'authority' ? 'rule--B' : 'proof-B');
    await utimes(target, fixedTime, fixedTime);
    const after = await stat(target);
    assert.equal(after.size, before.size);
    assert.equal(after.mtimeMs, before.mtimeMs);
    assert.equal((await f.controller.inspect()).action, kind === 'authority' ? 'authority_changed' : 'evidence_changed');
    await assert.rejects(f.controller.begin('second', 'changed-content'));
  });
}

test('resource conservation keeps state bytes and mtime unchanged on begin and finish replay', async (t) => {
  const f = await fixture(t);
  const stateFile = join(f.root, f.config.statePath);
  await f.controller.begin('first', 'no-rewrite');
  const fixedTime = new Date('2000-01-01T00:00:00.000Z');
  await utimes(stateFile, fixedTime, fixedTime);
  const runningBytes = await readFile(stateFile, 'utf8');
  const runningMtime = (await stat(stateFile)).mtimeMs;
  assert.equal((await f.controller.begin('first', 'no-rewrite')).replayed, true);
  assert.equal(await readFile(stateFile, 'utf8'), runningBytes);
  assert.equal((await stat(stateFile)).mtimeMs, runningMtime);
  const result = await f.pass('replayed-proof');
  const finished = await f.controller.finish('no-rewrite', result);
  await utimes(stateFile, fixedTime, fixedTime);
  const finishedBytes = await readFile(stateFile, 'utf8');
  const finishedMtime = (await stat(stateFile)).mtimeMs;
  assert.deepEqual(await f.controller.finish('no-rewrite', result), finished);
  assert.equal(await readFile(stateFile, 'utf8'), finishedBytes);
  assert.equal((await stat(stateFile)).mtimeMs, finishedMtime);
});

test('resource path-depth limit accepts 32 segments and rejects 33', async (t) => {
  const atLimit = Array(32).fill('part').join('/');
  const beyondLimit = `${atLimit}/extra`;
  const f = await fixture(t, { plan: { steps: [step('first', { scope: [atLimit] })] } });
  assert.equal((await f.controller.inspect()).action, 'continue');
  await assert.rejects(async () => {
    const c = await openContinuation({ ...f.config, statePath: beyondLimit });
    await c.inspect();
  });
  await f.put(f.config.planPath, JSON.stringify({ ...f.plan, steps: [step('first', { scope: [beyondLimit] })] }));
  await assert.rejects(f.controller.inspect());
});

test('representative inspect workload reports wall, CPU and logical reads without timing thresholds', async (t) => {
  const steps = Array.from({ length: 20 }, (_, index) => step(`measured-${index}`, {
    dependsOn: index === 0 ? [] : [`measured-${index - 1}`],
  }));
  const f = await fixture(t, { plan: { maxAttempts: 20, steps } });
  const proofBytes = 1024 * 1024;
  const evidence = await f.put('output/shared-measurement-proof.txt', 'p'.repeat(proofBytes));
  const result = { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence }] };
  for (const s of steps) {
    await f.controller.begin(s.id, `attempt-${s.id}`);
    await f.controller.finish(`attempt-${s.id}`, result);
  }
  const inputSizes = await Promise.all([f.config.planPath, f.layout.authority, f.config.statePath, evidence]
    .map(path => stat(join(f.root, path))));
  const expectedIo = { filesRead: 4, bytesRead: inputSizes.reduce((sum, info) => sum + info.size, 0) };
  const warm = await f.controller.inspect();
  assert.equal(warm.action, 'complete_pending_acceptance');
  assert.deepEqual(warm.io, expectedIo);

  // Fixture creation, warm-up and size checks are outside the measurement.
  // Retain samples and validate afterwards to minimize assertion overhead.
  const cpuBefore = process.cpuUsage();
  const wallBefore = process.hrtime.bigint();
  const samples = [];
  for (let index = 0; index < 10; index++) samples.push(await f.controller.inspect());
  const wallMs = Number(process.hrtime.bigint() - wallBefore) / 1e6;
  const cpu = process.cpuUsage(cpuBefore);
  for (const sample of samples) {
    assert.equal(sample.action, 'complete_pending_acceptance');
    assert.deepEqual(sample.io, expectedIo);
  }
  t.diagnostic(JSON.stringify({
    measurement: 'local component fixture; logical reads, not physical disk IO or production savings',
    environment: { node: process.version, os: platform(), release: release(), architecture: arch() },
    input: { passedSteps: steps.length, distinctEvidenceFiles: 1, evidenceBytes: proofBytes, distinctInputFiles: 4 },
    warmupInspections: 1,
    measuredInspections: samples.length,
    wallMs: Number(wallMs.toFixed(3)),
    cpuMs: { user: cpu.user / 1000, system: cpu.system / 1000 },
    logicalReadsPerInspection: samples.map(sample => sample.io),
  }));
});

test('state write budget rejects oversized finish without destroying the recoverable intent', async (t) => {
  const f = await fixture(t, { plan: { maxAttempts: 1000 } });
  const evidence = await f.put('output/historical-check.txt', 'Check was not executed.\n');
  const makeChecks = (count, suffixLength) => Array.from({ length: count }, (_, index) => ({
    id: `check-${String(index).padStart(3, '0')}-${'x'.repeat(suffixLength)}`,
    passed: false, evidence,
  }));
  const started = await f.controller.begin('first', 'template-attempt');
  const template = await f.controller.finish('template-attempt', {
    outcome: 'not_executed', checks: makeChecks(50, 40),
  });
  const stateFile = join(f.root, f.config.statePath);
  const originalState = JSON.parse(await readFile(stateFile, 'utf8'));
  const budget = 4 * 1024 * 1024;
  const pendingId = 'history-0999';
  const pending = { ...started.attempt, id: pendingId };
  const history = (count) => Array.from({ length: count }, (_, index) => ({
    ...template, id: `history-${String(index).padStart(4, '0')}`,
  }));
  const stateWith = attempts => ({ ...originalState, attempts });
  const encoded = state => `${JSON.stringify(state, null, 2)}\n`;
  const encodedSize = state => Buffer.byteLength(encoded(state));
  // Binary search bounds setup work: do not repeatedly serialize every growing
  // history prefix. Every historical entry is copied from a real valid finish.
  let low = 0, high = 998;
  while (low < high) {
    const count = Math.ceil((low + high) / 2);
    if (encodedSize(stateWith([...history(count), pending])) <= budget) low = count;
    else high = count - 1;
  }
  assert.ok(low >= 100 && low < 998, 'fixture must contain hundreds of valid historical attempts');
  const historicalAttempts = history(low);
  const largeResult = { outcome: 'not_executed', checks: makeChecks(100, 60) };
  const oversizedFinished = {
    ...pending, outcome: largeResult.outcome, result: largeResult,
    resultKey: createHash('sha256').update(JSON.stringify(largeResult)).digest('hex'),
    evidence: template.evidence,
  };
  assert.ok(encodedSize(stateWith([...historicalAttempts, pending])) <= budget);
  assert.ok(encodedSize(stateWith([...historicalAttempts, oversizedFinished])) > budget);
  await f.put(f.config.statePath, encoded(stateWith(historicalAttempts)));
  assert.equal((await f.controller.inspect()).action, 'continue');
  await f.controller.begin('first', pendingId);
  const before = await readFile(stateFile);
  assert.ok(before.length <= budget);
  await assert.rejects(f.controller.finish(pendingId, largeResult), { code: 'E_STATE_BUDGET' });
  assert.deepEqual(await readFile(stateFile), before);
  assert.equal((await f.controller.inspect()).action, 'reconcile');
});
