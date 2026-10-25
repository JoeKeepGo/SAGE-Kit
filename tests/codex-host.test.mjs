import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { openContinuation } from '../adapters/continuation.mjs';
import { createCodexHost, codexAvailable, codexSkipReason, nativeCall } from './helpers/codex-host.mjs';

const options = { skip: codexAvailable ? false : codexSkipReason, timeout: 40000 };
const step = (id, extra = {}) => ({ id, objective: `Produce ${id}`, dependsOn: [], scope: ['output'], checks: ['test'], requiresReview: false, admitted: true, humanGate: false, ...extra });
const begin = (stepId = 'first', attemptId = `attempt-${stepId}`) => nativeCall('sage_begin', { stepId, attemptId });
const finish = (checks = [{ id: 'test', passed: true, evidence: 'output/first.check' }]) => nativeCall('sage_finish', { attemptId: 'attempt-first', result: { outcome: 'passed', checks } });
const command = cmd => nativeCall('exec_command', { cmd, yield_time_ms: 1000, max_output_tokens: 1000 });
const work = () => command("mkdir -p output && printf 'actual-output' > output/first.txt && test \"$(cat output/first.txt)\" = 'actual-output' && printf 'verified actual-output' > output/first.check");
const quote = value => "'" + value.replaceAll("'", "'\"'\"'") + "'";
async function fixture(t, steps = [step('first')], hostOptions = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-codex-project-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = async (path, text) => { await mkdir(dirname(join(root, path)), { recursive: true }); await writeFile(join(root, path), text); };
  await put('docs/authority.md', 'Respect current authority; no publication.\n');
  const plan = { version: 1, goal: 'Native Codex governance fixture', authority: ['docs/authority.md'], constraints: ['Preserve user work', 'No network or publication'], maxAttempts: 30, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps };
  await put('plan.json', JSON.stringify(plan));
  const host = await createCodexHost(t, { projectRoot: root, ...hostOptions });
  const controller = await openContinuation({ root, planPath: 'plan.json', statePath: 'state.json' });
  return { root, host, controller, plan, put };
}
function successful(run) {
  assert.equal(run.code, 0, run.stderr + '\n' + run.stdout);
  assert.equal(run.unusedActions, 0, run.stdout);
  assert.deepEqual(run.unexpected, []);
  assert.ok(run.events.some(event => event.type === 'turn.completed'), run.stdout);
}
function calls(run) { return run.events.filter(event => event.type === 'item.completed' && event.item?.type === 'mcp_tool_call').map(event => event.item); }

test('Codex native hooks inject authority and actual MCP begin/work/finish reaches acceptance', options, async t => {
  const f = await fixture(t);
  const run = await f.host.run([begin(), work(), finish(), { text: 'Done with checked evidence; awaiting human acceptance.' }]);
  successful(run);
  assert.equal(await readFile(join(f.root, 'output/first.txt'), 'utf8'), 'actual-output');
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
  const initial = JSON.stringify(run.requests[0].input);
  for (const text of ['SAGE-Kit:', f.plan.goal, 'docs/authority.md', ...f.plan.constraints]) assert.ok(initial.includes(text), `Missing native injection: ${text}`);
  assert.ok(calls(run).some(call => call.tool === 'sage_begin'), run.stdout);
  assert.ok(calls(run).some(call => call.tool === 'sage_finish'), run.stdout);
  t.diagnostic('Actual native Codex binary + isolated HOME + loopback deterministic Responses model; adapter=' + (process.env.SAGE_AGENT_ADAPTER_DIR ? 'installed override' : 'staged source'));
});

test('Codex native guarded shell denial prevents unbegun effect and Stop reinjects governance', options, async t => {
  const f = await fixture(t);
  const denied = join(f.root, 'denied-effect');
  const run = await f.host.run([nativeCall('sage_inspect'), command(`printf forbidden > ${quote(denied)}`), { text: 'First stop attempt.' }, { text: 'Acknowledged pending work.' }]);
  successful(run);
  await assert.rejects(access(denied));
  assert.equal((await f.controller.inspect()).action, 'continue');
  assert.ok(run.requests.length >= 3, 'actual Stop hook must prevent the first premature completion');
  assert.match(JSON.stringify(run.requests.at(-1).input), /SAGE-Kit/);
});

test('Codex native failed evidence closes execution and does not admit downstream task', options, async t => {
  const f = await fixture(t, [step('first'), step('second', { dependsOn: ['first'] })]);
  const denied = join(f.root, 'after-invalid-finish');
  const run = await f.host.run([begin(), work(), finish([]), begin('second'), command(`printf forbidden > ${quote(denied)}`), { text: 'Evidence rejected.' }, { text: 'Await reconciliation.' }]);
  successful(run);
  await assert.rejects(access(denied));
  assert.equal((await f.controller.inspect()).action, 'reconcile');
  assert.ok(calls(run).filter(call => call.status === 'failed' || call.result?.isError).length >= 2, run.stdout);
});

test('Codex real process restart resumes session but replayed attempt cannot repeat side effect', options, async t => {
  const f = await fixture(t);
  const initial = await f.host.run([begin(), work(), { text: 'Pause with unfinished intent.' }, { text: 'Reconcile later.' }]);
  successful(initial);
  const id = initial.events.find(event => event.type === 'thread.started')?.thread_id;
  assert.ok(id);
  const denied = join(f.root, 'replayed-effect');
  const resumed = await f.host.run([begin(), command(`printf forbidden > ${quote(denied)}`), finish(), { text: 'Reconciled existing evidence.' }], { resume: id });
  successful(resumed);
  await assert.rejects(access(denied));
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
});


test('Codex native completed predecessor does not admit an unapproved next task', options, async t => {
  const f = await fixture(t, [step('first'), step('second', { dependsOn: ['first'], admitted: false })]);
  const denied = join(f.root, 'unadmitted-effect');
  const run = await f.host.run([begin(), work(), finish(), begin('second'), command(`printf forbidden > ${quote(denied)}`), { text: 'Next task awaits admission.' }]);
  successful(run);
  await assert.rejects(access(denied));
  assert.equal((await f.controller.inspect()).action, 'blocked');
  assert.ok(calls(run).some(call => call.tool === 'sage_begin' && call.arguments.stepId === 'second' && call.status === 'failed'), run.stdout);
});


test('Codex native 48-call bounded stress reuses one MCP process without state or idle writes', { ...options, skip: !codexAvailable ? codexSkipReason : process.platform !== 'linux' ? 'Linux /proc counters required' : false }, async t => {
  const f = await fixture(t);
  let before, after, idle;
  const seen = [];
  const start = performance.now();
  const script = Array.from({ length: 48 }, (_, index) => async request => {
    const sample = await f.host.sampleMcp();
    seen.push([sample.pid, sample.startTicks]);
    if (index === 0) {
      before = sample;
      await new Promise(resolve => setTimeout(resolve, 100));
      idle = await f.host.sampleMcp();
      assert.equal(idle.io.write_bytes, before.io.write_bytes, 'idle MCP must not write storage');
      assert.equal(idle.io.wchar, before.io.wchar, 'idle MCP must not emit writes');
      await assert.rejects(access(join(f.root, 'state.json')), { code: 'ENOENT' });
    }
    return nativeCall('sage_inspect')(request);
  });
  script.push(async () => { after = await f.host.sampleMcp(); return { text: 'Bounded inspection complete.' }; }, { text: 'Pending work remains under authority.' });
  const run = await f.host.run(script);
  successful(run);
  assert.equal(calls(run).length, 48);
  assert.ok(calls(run).every(call => call.tool === 'sage_inspect' && call.status === 'completed'));
  assert.ok(seen.every(([pid, ticks]) => pid === before.pid && ticks === before.startTicks));
  assert.equal(after.pid, before.pid);
  assert.equal(after.startTicks, before.startTicks, 'same PID must also be the same process lifetime');
  assert.equal(after.io.write_bytes, before.io.write_bytes, 'read-only inspection must not write storage');
  await assert.rejects(access(join(f.root, 'state.json')), { code: 'ENOENT' });
  const delta = (from, to) => ({ userTicks: to.userTicks - from.userTicks, systemTicks: to.systemTicks - from.systemTicks, io: Object.fromEntries(Object.keys(from.io).map(key => [key, to.io[key] - from.io[key]])) });
  t.diagnostic(JSON.stringify({ scenario: 'bounded native Codex stress; not production duration', calls: 48, requests: run.requests.length, wallMs: performance.now() - start, pid: before.pid, startTicks: before.startTicks, cpuUnits: 'Linux clock ticks', idle100ms: delta(before, idle), active: delta(idle, after), stateCreated: false }));
});


test('Codex native automatic compaction reinjects governance through the same MCP connection', options, async t => {
  const f = await fixture(t, [step('first')], { compactProbe: true });
  let before, after, resumedRequest;
  const run = await f.host.run([
    async request => {
      if (process.platform === 'linux') before = await f.host.sampleMcp();
      // Deterministic provider usage triggers the host's real automatic compact.
      return { ...begin()(request), forceCompact: true };
    },
    async request => {
      resumedRequest = request;
      if (process.platform === 'linux') after = await f.host.sampleMcp();
      return work()(request);
    },
    finish(), { text: 'Completed actual work after native compaction; awaiting acceptance.' },
  ]);
  successful(run);
  const compact = run.requests.filter(request => JSON.stringify(request.input).includes('You are performing a CONTEXT CHECKPOINT COMPACTION'));
  assert.equal(compact.length, 1, 'the actual native host must request one compaction');
  assert.equal(run.requests.length, 5, 'four scripted responses and one native compaction response');
  assert.ok(run.events.some(event => /multiple compactions/.test(event.item?.message ?? '')), 'native host must report actual compaction');
  const summaryIndex = resumedRequest.input.findIndex(message => JSON.stringify(message).includes('Compact summary: native fixture'));
  assert.ok(summaryIndex >= 0, 'native compacted summary replaces earlier history');
  assert.ok(!resumedRequest.input.some(message => message.type === 'function_call'), 'old begin tool history must be removed');
  const reminders = resumedRequest.input.slice(summaryIndex + 1).filter(message => message.role === 'developer' && JSON.stringify(message).includes('SAGE-Kit:'));
  assert.equal(reminders.length, 1, 'compact-only native MCP hook must inject fresh governance after the new summary');
  const reminder = JSON.stringify(reminders[0]);
  for (const required of [f.plan.goal, 'docs/authority.md', 'working', 'attempt-first']) assert.ok(reminder.includes(required), `Missing fresh compact context: ${required}`);
  if (before) assert.deepEqual([after.pid, after.startTicks], [before.pid, before.startTicks], 'compaction retains the original MCP process');
  assert.equal(await readFile(join(f.root, 'output/first.txt'), 'utf8'), 'actual-output');
  assert.equal((await f.controller.inspect()).action, 'complete_pending_acceptance');
  t.diagnostic('Actual native automatic compaction; deterministic local summary; compact-only MCP SessionStart hook restores working attempt, with real post-compact shell evidence.');
});
