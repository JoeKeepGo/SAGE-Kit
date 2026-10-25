import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { tmpdir, platform, arch } from 'node:os';
import { openContinuation } from '../adapters/continuation.mjs';
import { createDshRuntime, dshAvailable, dshSkipReason, toolResults, toolResultText, governanceMessages } from './helpers/dsh-runtime.mjs';

const options = { skip: dshAvailable ? false : dshSkipReason, timeout: 20000 };
const step = (id, overrides = {}) => ({ id, objective: `Produce ${id}`, dependsOn: [], scope: ['output'], checks: ['test'], requiresReview: false, admitted: true, humanGate: false, ...overrides });
const call = (tool, args = {}) => ({ tool, args });
const begin = (id = 'first', attemptId = `attempt-${id}`) => call('sage_begin', { stepId: id, attemptId });
const result = (id = 'first', extra = {}) => ({ outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: `output/${id}.check` }], ...extra });
const finish = (id = 'first', value = result(id), attemptId = `attempt-${id}`) => call('sage_finish', { attemptId, result: JSON.stringify(value) });

async function fixture(t, planOverrides = {}, pluginOverrides = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-dsh-project-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = async (path, text) => {
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), text);
  };
  await put('docs/authority.md', 'Keep project authority and required evidence. No publication.\n');
  const plan = { version: 1, goal: 'Complete admitted development under project governance', authority: ['docs/authority.md'], constraints: ['Preserve user work', 'No network or publication'], maxAttempts: 30, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps: [step('first')], ...planOverrides };
  await put('plan.json', JSON.stringify(plan));
  const config = { projectRoot: root, planPath: 'plan.json', statePath: 'state/progress.json', guardedTools: ['fixture_write'], ...pluginOverrides };
  const runtime = await createDshRuntime(t, config);
  const writes = [];
  const installFixtureTools = target => {
    target.register('fixture_write', async ({ id }, exec) => {
      exec.signal.throwIfAborted();
      writes.push(id);
      await put(`output/${id}.txt`, `delivered:${id}`);
      // This fixture check inspects the actual output before recording evidence.
      assert.equal(await readFile(join(root, `output/${id}.txt`), 'utf8'), `delivered:${id}`);
      await put(`output/${id}.check`, `Verified output/${id}.txt equals delivered:${id}\n`);
      return `delivered and checked ${id}`;
    }, { id: { type: 'string', required: true } });
    target.register('fixture_noop', async () => 'observed');
  };
  installFixtureTools(runtime);
  const controller = await openContinuation({ root, planPath: config.planPath, statePath: config.statePath });
  return { root, plan, put, config, runtime, writes, controller, installFixtureTools };
}

function successful(run) {
  assert.deepEqual(run.errors, []);
  assert.equal(run.unusedActions, 0, 'host must reach every scripted action');
  assert.equal(run.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
}

function allToolsPassed(run) {
  for (const entry of toolResults(run)) assert.notEqual(entry.message.isError, true, toolResultText(entry));
}

test('DSH staged adapter injects authority into the real stream and advances three checked tasks', options, async t => {
  const f = await fixture(t, { steps: [step('first'), step('second', { dependsOn: ['first'], requiresReview: true }), step('third', { dependsOn: ['second'] })] });
  const agent = await f.runtime.createAgent();
  const run = await f.runtime.run(agent, [
    begin(), call('fixture_write', { id: 'first' }), finish(),
    begin('second'), call('fixture_write', { id: 'second' }),
    async () => {
      assert.equal(await readFile(join(f.root, 'output/second.txt'), 'utf8'), 'delivered:second');
      await f.put('output/second.review', 'Fixture reviewer checked output equals expected second deliverable.\n');
      return finish('second', result('second', { review: 'output/second.review' }));
    },
    begin('third'), call('fixture_write', { id: 'third' }), finish('third'),
  ]);
  successful(run);
  allToolsPassed(run);
  assert.deepEqual(f.writes, ['first', 'second', 'third']);
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
  const request = JSON.stringify(run.requests[0]);
  for (const text of [f.plan.goal, ...f.plan.constraints, 'docs/authority.md', 'first']) assert.ok(request.includes(text), `missing governance context: ${text}`);
  const tools = run.requests[0].tools.map(tool => tool.name);
  for (const name of ['sage_inspect', 'sage_begin', 'sage_finish']) assert.ok(tools.includes(name));
});

test('DSH guarded tool does not run before an admitted begin', options, async t => {
  const f = await fixture(t);
  const run = await f.runtime.run(await f.runtime.createAgent(), [call('fixture_write', { id: 'first' })]);
  successful(run);
  assert.equal(toolResults(run)[0].message.isError, true);
  assert.deepEqual(f.writes, []);
  assert.equal((await f.controller.inspect()).action, 'continue');
});

test('DSH fresh session cannot obtain execution ownership by replaying an unfinished begin', options, async t => {
  const f = await fixture(t, { steps: [step('first'), step('second', { dependsOn: ['first'] })] });
  const first = await f.runtime.run(await f.runtime.createAgent(), [begin(), call('fixture_write', { id: 'first' })]);
  successful(first);
  allToolsPassed(first);
  const resumed = await f.runtime.createAgent();
  const replay = await f.runtime.run(resumed, [begin(), call('fixture_write', { id: 'first' }), finish(), begin('second'), call('fixture_write', { id: 'second' }), finish('second')]);
  successful(replay);
  assert.deepEqual(f.writes, ['first', 'second'], 'unfinished side effect must not be repeated after session switch');
  assert.ok(toolResults(replay).some(entry => entry.message.isError === true));
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
});

test('DSH disposed and rebuilt Cordis host reconciles durable intent without repeating effects', options, async t => {
  const f = await fixture(t, { steps: [step('first'), step('second', { dependsOn: ['first'] })] });
  const initial = await f.runtime.run(await f.runtime.createAgent(), [begin(), call('fixture_write', { id: 'first' })]);
  successful(initial);
  allToolsPassed(initial);
  assert.equal((await f.controller.inspect()).action, 'reconcile');
  await f.runtime.dispose();
  const restored = await createDshRuntime(t, f.config);
  f.installFixtureTools(restored);
  const run = await restored.run(await restored.createAgent(), [
    begin(), call('fixture_write', { id: 'first' }),
    async () => {
      assert.equal(await readFile(join(f.root, 'output/first.txt'), 'utf8'), 'delivered:first');
      return finish();
    },
    begin('second'), call('fixture_write', { id: 'second' }), finish('second'),
  ]);
  successful(run);
  assert.equal(toolResults(run)[1].message.isError, true);
  assert.deepEqual(f.writes, ['first', 'second']);
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
});

for (const required of ['check', 'review']) {
  test(`DSH missing required ${required} blocks finish and downstream admission`, options, async t => {
    const f = await fixture(t, { steps: [step('first', { requiresReview: required === 'review' }), step('second', { dependsOn: ['first'] })] });
    const invalid = required === 'check' ? { outcome: 'passed', checks: [] } : result();
    const run = await f.runtime.run(await f.runtime.createAgent(), [begin(), call('fixture_write', { id: 'first' }), finish('first', invalid), begin('second')]);
    successful(run);
    const results = toolResults(run);
    assert.equal(results[2].message.isError, true, 'finish must reject missing evidence');
    assert.equal(results[3].message.isError, true, 'downstream begin must reject');
    assert.deepEqual(f.writes, ['first']);
    assert.equal((await f.controller.inspect()).action, 'reconcile');
  });
}

test('DSH human admission gate stops guarded effects', options, async t => {
  const f = await fixture(t, { steps: [step('first', { humanGate: true })] });
  const run = await f.runtime.run(await f.runtime.createAgent(), [begin(), call('fixture_write', { id: 'first' })]);
  assert.deepEqual(f.writes, []);
  assert.equal((await f.controller.inspect()).action, 'human_gate');
  assert.ok(run.requests.length === 0 || toolResults(run).every(entry => entry.message.isError === true));
});

test('DSH changed authority ends active execution before another guarded effect', options, async t => {
  const f = await fixture(t);
  const agent = await f.runtime.createAgent();
  const started = await f.runtime.run(agent, [begin()]);
  successful(started);
  await f.put('docs/authority.md', 'Changed authority: this round is no longer valid.\n');
  const stopped = await f.runtime.run(agent, [call('fixture_write', { id: 'first' })]);
  assert.deepEqual(f.writes, []);
  assert.equal((await f.controller.inspect()).action, 'authority_changed');
  assert.ok(stopped.requests.length === 0 || toolResults(stopped).every(entry => entry.message.isError === true));
});

test('DSH long unchanged step sequence bounds governance injections and reinjects after actual surface replacement', options, async t => {
  const f = await fixture(t, { steps: [step('history'), step('first', { dependsOn: ['history'] })] }, { remindEverySteps: 8 });
  await f.controller.begin('history', 'recorded-history');
  await f.put('output/history.check', 'History check evidence.\n' + 'x'.repeat(64 * 1024));
  await f.controller.finish('recorded-history', result('history'));
  const agent = await f.runtime.createAgent();
  const cpuStart = process.cpuUsage(), wallStart = performance.now();
  const run = await f.runtime.run(agent, Array.from({ length: 24 }, () => call('fixture_noop')));
  const cpu = process.cpuUsage(cpuStart), wallMs = performance.now() - wallStart;
  successful(run);
  const reads = run.diagnostics.filter(event => event.io);
  const observations = reads.filter(event => event.operation === 'observe');
  const inspections = reads.filter(event => event.operation === 'inspect');
  assert.ok(observations.length >= 20, 'ordinary steps must use lightweight observation');
  assert.ok(inspections.length >= 1 && inspections.length <= 2, 'unchanged steps must not repeatedly scan historical evidence');
  assert.ok(observations.every(event => event.io.filesRead === 3 && event.io.bytesRead < 16 * 1024));
  assert.ok(inspections.some(event => event.io.bytesRead > 64 * 1024), 'initial full inspection must really verify history');
  const injected = governanceMessages(run);
  t.diagnostic(JSON.stringify({ evidence: 'real DSH components + deterministic model double', node: process.version, platform: platform(), arch: arch(), projectRoot: f.root, requests: run.requests.length, historyEvidenceBytes: 64 * 1024, wallMs, cpuUserMs: cpu.user / 1000, cpuSystemMs: cpu.system / 1000, logicalBytesRead: reads.reduce((sum, event) => sum + event.io.bytesRead, 0), logicalFilesRead: reads.reduce((sum, event) => sum + event.io.filesRead, 0), injections: injected.length }));
  assert.ok(injected.length >= 1 && injected.length <= 5, `25 steps injected ${injected.length} governance messages`);
  // Replace while the same turn is running: a new-turn reminder alone must
  // not make this test pass when replacement generation handling is broken.
  let replacementRequest;
  const resumed = await f.runtime.run(agent, [
    call('fixture_noop'),
    () => {
      f.runtime.replaceGovernance(agent);
      return call('fixture_noop');
    },
    request => {
      replacementRequest = request;
      return call('fixture_noop');
    },
  ]);
  successful(resumed);
  assert.equal(governanceMessages(resumed).length, 2, 'new turn plus same-turn replacement must each inject once');
  assert.ok(JSON.stringify(replacementRequest).includes(f.plan.goal));
  assert.equal((await f.controller.inspect()).action, 'continue');
});
