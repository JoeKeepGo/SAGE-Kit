// Child-only real DSH fixture: killed after intent and a checked side effect,
// while the guarded tool body has not returned. No profile/provider is loaded.
import assert from 'node:assert/strict';
import { appendFile, readFile, writeFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import { createDshRuntime } from '../helpers/dsh-runtime.mjs';

const config = JSON.parse(await readFile(process.argv[2], 'utf8'));
const cleanup = [];
const watchdog = setTimeout(() => {
  console.error('DSH interrupt fixture exceeded its process deadline');
  process.exit(2);
}, 12000);
try {
  const runtime = await createDshRuntime({ after: fn => cleanup.push(fn) }, config);
  runtime.register('fixture_write', async (_args, exec) => {
    exec.signal.throwIfAborted();
    await appendFile(join(config.projectRoot, 'output/effects.txt'), 'first\n');
    assert.equal(await readFile(join(config.projectRoot, 'output/effects.txt'), 'utf8'), 'first\n');
    await writeFile(join(config.projectRoot, 'output/first.check'), 'Read effects.txt and verified exactly one first effect.\n');
    const state = JSON.parse(await readFile(join(config.projectRoot, config.statePath), 'utf8'));
    assert.equal(state.attempts.find(attempt => attempt.id === 'attempt-first')?.outcome, 'running');
    const snapshot = { point: 'guarded body after side effect and check, before tool return or sage_finish', pid: process.pid, requests: runtime.requests, events: runtime.events, errors: runtime.errors.map(item => String(item.error)) };
    await writeFile(join(config.projectRoot, 'ready.tmp'), JSON.stringify(snapshot));
    await rename(join(config.projectRoot, 'ready.tmp'), join(config.projectRoot, 'ready.json'));
    // The parent observes the durable ready file, then SIGKILLs this process.
    // A timeout/cancellation remains cooperative if the parent fails to kill.
    await new Promise((_, reject) => {
      if (exec.signal.aborted) return reject(exec.signal.reason);
      exec.signal.addEventListener('abort', () => reject(exec.signal.reason), { once: true });
    });
    return 'unreachable';
  });
  const run = await runtime.run(await runtime.createAgent(), [
    { tool: 'sage_begin', args: { stepId: 'first', attemptId: 'attempt-first' } },
    { tool: 'fixture_write' },
  ]);
  throw new Error(`Interrupt fixture ended before parent SIGKILL: ${JSON.stringify(run.errors.map(item => String(item.error)))}`);
} finally {
  clearTimeout(watchdog);
  for (const dispose of cleanup.reverse()) await dispose();
}
