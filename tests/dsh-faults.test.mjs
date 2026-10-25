import test from 'node:test';
import assert from 'node:assert/strict';
import fileSystem, { mkdtemp, mkdir, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { syncBuiltinESMExports } from 'node:module';
import { setTimeout as delay } from 'node:timers/promises';
import { openContinuation } from '../adapters/continuation.mjs';
import { createDshRuntime, dshAvailable, dshSkipReason, toolResults, toolResultText, governanceMessages } from './helpers/dsh-runtime.mjs';

const options = { skip: dshAvailable ? false : dshSkipReason, timeout: 20000 };
const call = (tool, args = {}) => ({ tool, args });
const begin = () => call('sage_begin', { stepId: 'first', attemptId: 'first-attempt' });

async function fixture(t, planOverrides = {}, pluginOverrides = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-dsh-fault-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = async (path, value) => {
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), value);
  };
  await put('docs/authority.md', 'Preserve project rules and require real checks.\n');
  const plan = {
    version: 1, goal: 'Advance only admitted work', authority: ['docs/authority.md'],
    constraints: ['No network or publication'], maxAttempts: 10,
    expiresAt: '2099-01-01T00:00:00.000Z', revoked: false,
    steps: [{ id: 'first', objective: 'Produce fixture output', dependsOn: [], scope: ['output'],
      checks: ['test'], requiresReview: false, admitted: true, humanGate: false }],
    ...planOverrides,
  };
  await put('plan.json', JSON.stringify(plan));
  const runtime = await createDshRuntime(t, {
    projectRoot: root, planPath: 'plan.json', statePath: 'state/progress.json',
    guardedTools: ['fixture_write'], ...pluginOverrides,
  });
  const writes = [];
  runtime.register('fixture_write', async (_args, exec) => {
    exec.signal.throwIfAborted();
    writes.push('write');
    await put('output/effect.txt', 'side effect happened\n');
    return 'wrote fixture output';
  });
  return { root, put, runtime, writes };
}

async function noExecution(f, run) {
  assert.equal(run.requests.length, 0, 'rejected pre-step must not reach the model transport');
  assert.deepEqual(f.writes, []);
  assert.equal(toolResults(run).length, 0);
  assert.notEqual(run.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
  await assert.rejects(stat(join(f.root, 'output/effect.txt')), { code: 'ENOENT' });
}

// Instrument a real FileHandle, delaying just the first read rather than
// replacing read contents. This lets the event loop run the real deadline or
// agent cancellation while one filesystem operation is pending.
function delayedRead(t, f, { delayMs, onRead }) {
  const target = join(f.root, 'docs/authority.md');
  const originalOpen = fileSystem.open;
  const stats = { opened: [], reads: 0, closes: 0, completedReads: 0 };
  const mock = t.mock.method(fileSystem, 'open', async (...args) => {
    const path = String(args[0]);
    if (path.startsWith(f.root + '/')) stats.opened.push(path);
    const handle = await originalOpen(...args);
    if (path === target) {
      const read = handle.read.bind(handle), close = handle.close.bind(handle);
      handle.read = async (...readArgs) => {
        stats.reads++;
        if (stats.reads === 1) {
          await onRead?.();
          if (delayMs !== undefined) await delay(delayMs);
        }
        const value = await read(...readArgs);
        stats.completedReads++;
        return value;
      };
      handle.close = async () => { await close(); stats.closes++; };
    }
    return handle;
  });
  syncBuiltinESMExports();
  t.after(() => { mock.mock.restore(); syncBuiltinESMExports(); });
  return stats;
}

test('DSH oversized legal governance context fails closed without truncation or execution', options, async t => {
  const f = await fixture(t, { goal: 'Explicit governance condition. '.repeat(90) }, { maxContextBytes: 1024 });
  const agent = await f.runtime.createAgent();
  const run = await f.runtime.run(agent, [begin(), call('fixture_write')]);
  await noExecution(f, run);
  assert.equal(governanceMessages(run).length, 0, 'no truncated governance message may be injected');
  assert.ok(run.diagnostics.some(event => event.operation === 'pre-step-error' && event.code === 'E_CONTEXT_BUDGET'));
});

test('DSH missing authority rejects pre-step before requests or guarded effects', options, async t => {
  const f = await fixture(t);
  const agent = await f.runtime.createAgent();
  await rm(join(f.root, 'docs/authority.md'));
  const run = await f.runtime.run(agent, [begin(), call('fixture_write')]);
  await noExecution(f, run);
  assert.ok(run.diagnostics.some(event => event.operation === 'pre-step-error' && event.code === 'ENOENT'));
});

test('DSH deadline abort settles the pending read and never scans later blocks or files', options, async t => {
  const f = await fixture(t, { authority: ['docs/authority.md', 'docs/later.md'] }, { deadlineMs: 100 });
  await f.put('docs/authority.md', 'x'.repeat(1024 * 1024));
  await f.put('docs/later.md', 'This file must never be opened after the deadline.');
  const agent = await f.runtime.createAgent();
  // Synchronize this fault at the intended boundary. CI can spend the entire
  // 100ms budget opening earlier files, which would test an earlier abort instead.
  // Only the clock's start is controlled: the real native timeout/reason and the
  // product's AbortSignal.any cancellation/settlement path remain in use.
  const nativeTimeout = AbortSignal.timeout.bind(AbortSignal);
  const pendingDeadline = new AbortController(), requested = [];
  const timeout = t.mock.method(AbortSignal, 'timeout', ms => {
    if (ms !== 100) return nativeTimeout(ms);
    requested.push(ms);
    return pendingDeadline.signal;
  });
  t.after(() => timeout.mock.restore());
  let timeoutReason;
  const stats = delayedRead(t, f, { onRead: async () => {
    assert.deepEqual(requested, [100], 'the plugin must request its configured deadline');
    assert.equal(pendingDeadline.signal.aborted, false, 'the read must begin before cancellation');
    const deadline = nativeTimeout(100);
    await new Promise(resolve => deadline.addEventListener('abort', () => {
      timeoutReason = deadline.reason;
      pendingDeadline.abort(timeoutReason);
      resolve();
    }, { once: true }));
  } });
  const run = await f.runtime.run(agent, [begin(), call('fixture_write')]);
  await noExecution(f, run);
  assert.deepEqual(requested, [100]);
  assert.equal(timeoutReason?.name, 'TimeoutError', 'use the actual native deadline reason');
  assert.equal(stats.reads, 1, 'deadline must stop before a second 64 KiB chunk');
  assert.equal(stats.completedReads, 1);
  assert.equal(stats.closes, 1, 'turn must settle the pending reader, not leave a Promise.race loser');
  assert.equal(stats.opened.includes(join(f.root, 'docs/later.md')), false);
  assert.equal(stats.opened.includes(join(f.root, 'state/progress.json')), false);
  assert.ok(run.diagnostics.some(event => event.operation === 'pre-step-error' && event.code === timeoutReason.code));
  assert.equal(run.diagnostics.some(event => event.operation === 'inspect' && event.io), false);
  const snapshot = JSON.stringify(stats);
  await delay(40);
  assert.equal(JSON.stringify(stats), snapshot, 'no background read should survive rejection');
});

test('DSH real agent.cancel during pre-step read cooperatively stops instead of granting execution', options, async t => {
  const f = await fixture(t, { authority: ['docs/authority.md', 'docs/later.md'] }, { deadlineMs: 2000 });
  await f.put('docs/authority.md', 'x'.repeat(1024 * 1024));
  await f.put('docs/later.md', 'This file must never be opened after cancellation.');
  const agent = await f.runtime.createAgent();
  let cancellations = 0;
  const stats = delayedRead(t, f, { delayMs: 120, onRead: () => {
    cancellations++;
    agent.cancel({ kind: 'user' });
  } });
  const run = await f.runtime.run(agent, [begin(), call('fixture_write')]);
  await noExecution(f, run);
  assert.equal(cancellations, 1, 'the real Agent cancellation API must have been reached');
  assert.equal(stats.reads, 1);
  assert.equal(stats.completedReads, 1);
  assert.equal(stats.closes, 1);
  assert.equal(stats.opened.includes(join(f.root, 'docs/later.md')), false);
  assert.equal(run.diagnostics.some(event => event.operation === 'inspect' && event.io), false);
  const snapshot = JSON.stringify(stats);
  await delay(40);
  assert.equal(JSON.stringify(stats), snapshot);
});

test('DSH preserves another plugin denial even after valid ownership is acquired', options, async t => {
  const f = await fixture(t);
  const agent = await f.runtime.createAgent();
  await f.runtime.ctx.plugin({ name: 'fixture-independent-denial', apply(ctx) {
    ctx.on('tools/pre-execute', async (exec, next) => {
      const previous = await next();
      return exec.name === 'fixture_write' ? { kind: 'deny', reason: 'Independent fixture permission denied' } : previous;
    });
  } });
  const run = await f.runtime.run(agent, [begin(), call('fixture_write')]);
  assert.deepEqual(run.errors, []);
  assert.equal(run.unusedActions, 0);
  const results = toolResults(run);
  assert.notEqual(results[0].message.isError, true, toolResultText(results[0]));
  assert.equal(results[1].message.isError, true);
  assert.match(toolResultText(results[1]), /Independent fixture permission denied/);
  assert.deepEqual(f.writes, []);
  await assert.rejects(stat(join(f.root, 'output/effect.txt')), { code: 'ENOENT' });
});

test('DSH same-session replay revokes execution ownership instead of repeating the side effect', options, async t => {
  const f = await fixture(t);
  const run = await f.runtime.run(await f.runtime.createAgent(), [begin(), call('fixture_write'), begin(), call('fixture_write')]);
  assert.deepEqual(run.errors, []);
  assert.equal(run.unusedActions, 0);
  const results = toolResults(run);
  assert.equal(JSON.parse(toolResultText(results[2])).replayed, true);
  assert.equal(results[3].message.isError, true);
  assert.deepEqual(f.writes, ['write']);
  assert.equal(await readFile(join(f.root, 'output/effect.txt'), 'utf8'), 'side effect happened\n');
});

test('DSH failed inspection clears ownership before the next guarded tool in the same response', options, async t => {
  const f = await fixture(t);
  const authority = await readFile(join(f.root, 'docs/authority.md'));
  const run = await f.runtime.run(await f.runtime.createAgent(), [begin(), async () => {
    // The real pre-step has just passed. Both calls below belong to one model
    // response, so no later pre-step can rescue an ownership invalidation bug.
    await rm(join(f.root, 'docs/authority.md'));
    return { tools: [call('sage_inspect'), call('fixture_write')] };
  }]);
  const results = toolResults(run);
  assert.equal(run.unusedActions, 0);
  assert.equal(run.requests.length, 2);
  assert.equal(results.length, 3, 'scheduler must reach both tools in the same response');
  assert.equal(JSON.parse(toolResultText(results[0])).replayed, false);
  assert.equal(results[1].message.isError, true);
  assert.match(toolResultText(results[1]), /ENOENT|no such file/i);
  assert.equal(results[2].message.isError, true);
  assert.match(toolResultText(results[2]), /SAGE-Kit requires a fresh admitted intent/);
  assert.ok(run.diagnostics.some(event => event.operation === 'sage_inspect' && event.code === 'ENOENT'));
  assert.deepEqual(f.writes, []);
  await assert.rejects(stat(join(f.root, 'output/effect.txt')), { code: 'ENOENT' });
  const state = JSON.parse(await readFile(join(f.root, 'state/progress.json'), 'utf8'));
  assert.equal(state.attempts.length, 1);
  assert.equal(state.attempts[0].id, 'first-attempt');
  assert.equal(state.attempts[0].outcome, 'running');
  const controller = await openContinuation({ root: f.root, planPath: 'plan.json', statePath: 'state/progress.json' });
  await assert.rejects(controller.inspect(), { code: 'ENOENT' });
  await f.put('docs/authority.md', authority);
  assert.equal((await controller.inspect()).action, 'reconcile');
});

test('DSH downstream ask cannot bypass the missing-begin gate or reach approval', options, async t => {
  const f = await fixture(t);
  let asks = 0, approvalRequests = 0;
  await f.runtime.ctx.plugin({ name: 'fixture-independent-ask', apply(ctx) {
    // If the SAGE gate accidentally forwards ask, this service would grant it.
    // Thus an unavailable approval service cannot make a bypass look safe.
    ctx.provide('approval', { async request() {
      approvalRequests++;
      return 'allowed-once';
    } });
    ctx.on('tools/pre-execute', async (exec, next) => {
      const previous = await next();
      if (exec.name !== 'fixture_write') return previous;
      asks++;
      return { kind: 'ask', reason: 'Independent plugin requests human approval' };
    });
  } });
  assert.equal(typeof f.runtime.ctx.get('approval')?.request, 'function');
  const run = await f.runtime.run(await f.runtime.createAgent(), [call('fixture_write')]);
  assert.deepEqual(run.errors, []);
  assert.equal(run.unusedActions, 0);
  assert.equal(asks, 1);
  assert.equal(approvalRequests, 0, 'missing intent must deny before approval can grant the tool');
  const results = toolResults(run);
  assert.equal(results.length, 1);
  assert.equal(results[0].message.isError, true);
  assert.match(toolResultText(results[0]), /SAGE-Kit requires a fresh admitted intent/);
  assert.deepEqual(f.writes, []);
  await assert.rejects(stat(join(f.root, 'output/effect.txt')), { code: 'ENOENT' });
});
