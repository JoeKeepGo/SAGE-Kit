import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, appendFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { openContinuation } from '../adapters/continuation.mjs';
import { createDshRuntime, dshAvailable, dshSkipReason, toolResults, toolResultText } from './helpers/dsh-runtime.mjs';

const skip = !dshAvailable ? dshSkipReason : process.platform === 'win32' ? 'This fixture asserts POSIX SIGKILL; Windows process-tree recovery is not covered.' : false;
const call = (tool, args = {}) => ({ tool, args });
const checked = id => ({ outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: `output/${id}.check` }] });

test('DSH SIGKILL after guarded side effect recovers intent without replaying the effect', { skip, timeout: 20000 }, async t => {
  const root = await mkdtemp(join(tmpdir(), 'sage-dsh-sigkill-'));
  await mkdir(join(root, 'output'));
  await mkdir(join(root, 'child-tmp'));
  await writeFile(join(root, 'authority.md'), 'Preserve actual effects; reconcile interrupted intent before continuing.\n');
  const step = (id, dependsOn) => ({ id, objective: `Produce ${id}`, dependsOn, scope: ['output'], checks: ['test'], requiresReview: false, admitted: true, humanGate: false });
  await writeFile(join(root, 'plan.json'), JSON.stringify({ version: 1, goal: 'Complete two bounded effects without duplicates', authority: ['authority.md'], constraints: ['No network', 'Reconcile unknown outcomes'], maxAttempts: 3, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps: [step('first', []), step('second', ['first'])] }));
  const config = { projectRoot: root, planPath: 'plan.json', statePath: 'state/progress.json', guardedTools: ['fixture_write'] };
  const configFile = join(root, 'child-config.json');
  await writeFile(configFile, JSON.stringify(config));
  const env = { ...process.env, TMPDIR: join(root, 'child-tmp') };
  delete env.NODE_TEST_CONTEXT;
  const child = spawn(process.execPath, [fileURLToPath(new URL('./fixtures/dsh-interrupt.mjs', import.meta.url)), configFile], { env, stdio: ['ignore', 'ignore', 'pipe'] });
  let stderr = '', spawnError, restored;
  child.stderr.on('data', data => { stderr = (stderr + data).slice(-16000); });
  child.once('error', error => { spawnError = error; });
  const closed = new Promise(resolve => child.once('close', (code, signal) => resolve({ code, signal })));
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
    await closed;
    await restored?.dispose();
    await rm(root, { recursive: true, force: true });
  });
  let ready;
  const deadline = Date.now() + 6000;
  while (!ready) {
    if (spawnError) throw spawnError;
    try { ready = JSON.parse(await readFile(join(root, 'ready.json'), 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (ready) break;
    if (child.exitCode !== null || child.signalCode !== null) throw new Error(`Child exited before ready: ${child.exitCode}/${child.signalCode}\n${stderr}`);
    if (Date.now() >= deadline) throw new Error(`Child failed to reach durable ready point\n${stderr}`);
    await delay(20);
  }
  assert.equal(ready.pid, child.pid);
  assert.deepEqual(ready.errors, []);
  assert.equal(ready.requests.length, 2);
  assert.ok(ready.events.some(event => event.type === 'tool/call' && event.data.name === 'fixture_write'));
  assert.equal(child.exitCode, null);
  assert.equal(child.kill('SIGKILL'), true);
  assert.deepEqual(await closed, { code: null, signal: 'SIGKILL' });
  assert.equal(await readFile(join(root, 'output/effects.txt'), 'utf8'), 'first\n');
  const controller = await openContinuation({ root, planPath: config.planPath, statePath: config.statePath });
  assert.equal((await controller.inspect()).action, 'reconcile');

  restored = await createDshRuntime(t, config);
  let executedAfterRestart = 0;
  restored.register('fixture_write', async ({ id }, exec) => {
    exec.signal.throwIfAborted();
    executedAfterRestart++;
    await appendFile(join(root, 'output/effects.txt'), `${id}\n`);
    const content = await readFile(join(root, 'output/effects.txt'), 'utf8');
    assert.equal(content, 'first\nsecond\n');
    await writeFile(join(root, `output/${id}.check`), 'Verified effects.txt contains first then second exactly once.\n');
    return `checked ${id}`;
  }, { id: { type: 'string', required: true } });
  const run = await restored.run(await restored.createAgent(), [
    call('sage_begin', { stepId: 'first', attemptId: 'attempt-first' }),
    call('fixture_write', { id: 'first' }),
    async () => {
      assert.equal(await readFile(join(root, 'output/effects.txt'), 'utf8'), 'first\n');
      assert.match(await readFile(join(root, 'output/first.check'), 'utf8'), /exactly one/);
      return call('sage_finish', { attemptId: 'attempt-first', result: JSON.stringify(checked('first')) });
    },
    call('sage_begin', { stepId: 'second', attemptId: 'attempt-second' }),
    call('fixture_write', { id: 'second' }),
    call('sage_finish', { attemptId: 'attempt-second', result: JSON.stringify(checked('second')) }),
  ]);
  assert.deepEqual(run.errors, []);
  assert.equal(run.unusedActions, 0);
  const results = toolResults(run);
  assert.equal(JSON.parse(toolResultText(results[0])).replayed, true);
  assert.equal(results[1].message.isError, true);
  for (const entry of results.slice(2)) assert.notEqual(entry.message.isError, true, toolResultText(entry));
  assert.equal(executedAfterRestart, 1);
  assert.equal(await readFile(join(root, 'output/effects.txt'), 'utf8'), 'first\nsecond\n');
  assert.equal((await controller.inspect()).action, 'complete_pending_acceptance');
  assert.equal(run.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
  t.diagnostic(`POSIX SIGKILL point: ${ready.point}; no state lock was held by the guarded body. Restart used a new real Cordis/DSH context with the same project state. This does not cover Windows process trees or killing a state mutation while its lock is held.`);
});
