import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { setTimeout as delay } from 'node:timers/promises';
import { openAgentHost, readConfig } from '../adapters/agent-host.mjs';

async function fixture(t, extra = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-host-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = (p, data) => writeFile(join(root, p), typeof data === 'string' ? data : JSON.stringify(data));
  const plan = { version: 1, goal: 'Bounded authorized work', authority: ['SPEC.md'], constraints: ['No remote writes'], maxAttempts: 6, expiresAt: '2099-01-01T00:00:00Z', revoked: false,
    steps: [{ id: 'one', objective: 'Deliver one', dependsOn: [], scope: ['output'], checks: ['check'], requiresReview: false, admitted: true, humanGate: false },
      { id: 'gate', objective: 'Human choice', dependsOn: ['one'], scope: ['output'], checks: [], requiresReview: false, admitted: true, humanGate: true }] };
  const config = { host: 'codex', projectRoot: root, planPath: 'plan.json', statePath: 'state.json', guardedTools: ['Write'], ...extra };
  await put('SPEC.md', 'Preserve governance and actual evidence.'); await put('plan.json', plan); await put('config.json', config);
  const event = (kind, fields = {}) => ({ hook_event_name: kind, cwd: root, session_id: 'one-session', ...fields });
  return { root, config, plan, put, event, configPath: join(root, 'config.json') };
}
const denied = v => assert.equal(v.hookSpecificOutput.permissionDecision, 'deny');
const begin = h => h.call('sage_begin', { stepId: 'one', attemptId: 'first' });

test('host reminder, bounded execution, required evidence and human gate share continuation semantics', async t => {
  const f = await fixture(t), h = await openAgentHost(f.config);
  const hook = fields => h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write', ...fields }) });
  assert.match((await h.call('sage_hook', { event: f.event('SessionStart', { source: 'startup' }) })).hookSpecificOutput.additionalContext, /Bounded authorized work/);
  denied(await hook()); await begin(h); assert.deepEqual(await hook(), {});
  await assert.rejects(h.call('sage_finish', { attemptId: 'first', result: { outcome: 'passed', checks: [] } }));
  denied(await hook());
  await f.put('check.txt', 'Actual check fixture');
  await h.call('sage_finish', { attemptId: 'first', result: { outcome: 'passed', checks: [{ id: 'check', passed: true, evidence: 'check.txt' }] } });
  assert.equal((await h.call('sage_inspect')).action, 'human_gate');
  await assert.rejects(h.call('sage_begin', { stepId: 'gate', attemptId: 'second' }), /human_gate/);
});

for (const cause of ['replay', 'reconnect', 'resume', 'interrupt', 'authority', 'revoked', 'session', 'outside', 'bad_args']) {
  test(`${cause} cannot preserve an execution marker`, async t => {
    const f = await fixture(t); let h = await openAgentHost(f.config);
    await h.call('sage_hook', { event: f.event('UserPromptSubmit') }); await begin(h);
    if (cause === 'replay') assert.equal((await begin(h)).replayed, true);
    if (cause === 'reconnect') h = await openAgentHost(f.config);
    if (cause === 'resume') await h.call('sage_hook', { event: f.event('SessionStart', { source: 'resume' }) });
    if (cause === 'interrupt') await h.call('sage_hook', { event: f.event('Interrupt') });
    if (cause === 'authority') await f.put('SPEC.md', 'Changed authority');
    if (cause === 'revoked') await f.put('plan.json', { ...f.plan, revoked: true });
    if (cause === 'session') await h.call('sage_hook', { event: f.event('UserPromptSubmit', { session_id: 'other' }) });
    if (cause === 'outside') await h.call('sage_hook', { event: f.event('UserPromptSubmit', { cwd: tmpdir() }) });
    if (cause === 'bad_args') await assert.rejects(h.call('sage_begin', { stepId: 'one', attemptId: 'bad', approve: true }));
    denied(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) }));
  });
}

test('compact refresh preserves current owner; Stop offers only one continuation and never marks completion', async t => {
  const f = await fixture(t), h = await openAgentHost(f.config);
  await begin(h);
  assert.match((await h.call('sage_hook', { event: f.event('SessionStart', { source: 'compact' }) })).hookSpecificOutput.additionalContext, /working/);
  assert.deepEqual(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) }), {});
  assert.equal((await h.call('sage_hook', { event: f.event('Stop') })).decision, 'block');
  assert.equal((await h.call('sage_hook', { event: f.event('Stop', { stop_hook_active: true }) })).decision, undefined);
  assert.equal((await h.call('sage_inspect')).action, 'reconcile');
});

test('read-only repeated hooks bound IO, do not rewrite state or scan historical proofs on every tool', async t => {
  const f = await fixture(t), samples = [], h = await openAgentHost(f.config, { diagnostic: v => samples.push(v) });
  await begin(h); await h.call('sage_inspect');
  const before = await stat(join(f.root, 'state.json'));
  const cpu = process.cpuUsage(), start = performance.now();
  for (let i = 0; i < 100; i++) assert.deepEqual(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) }), {});
  const measured = process.cpuUsage(cpu);
  const records = samples.slice(-100);
  assert.ok(records.every(s => s.io.filesRead === 3));
  assert.equal((await stat(join(f.root, 'state.json'))).mtimeMs, before.mtimeMs);
  assert.equal((await stat(join(f.root, 'state.json'))).size, before.size);
  const count = samples.length;
  for (let i = 0; i < 20; i++) await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Read' }) });
  await delay(30); assert.equal(samples.length, count);
  t.diagnostic(JSON.stringify({ sample: '100 selected tool hooks; three small files each', elapsedMs: performance.now() - start, cpu: measured, bytesRead: records.reduce((s, x) => s + x.io.bytesRead, 0), filesRead: 300, stateRewrites: 0 }));
});

test('context budget and malformed governance return a normal denial without truncating or granting', async t => {
  const f = await fixture(t, { maxContextBytes: 1024 });
  f.plan.constraints = Array(20).fill('a'.repeat(200)); await f.put('plan.json', f.plan);
  const h = await openAgentHost(f.config);
  const answer = await h.call('sage_hook', { event: f.event('UserPromptSubmit') });
  assert.equal(answer.continue, false); assert.match(answer.systemMessage, /E_CONTEXT_BUDGET/);
  await f.put('plan.json', 'not JSON');
  denied(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) }));
});

test('malformed hook arguments and missing tool identity return normal deny, never MCP isError', async t => {
  const f = await fixture(t), h = await openAgentHost(f.config);
  await begin(h);
  denied(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }), extra: true }));
  denied(await h.call('sage_hook', { event: f.event('PreToolUse') }));
  denied(await h.call('sage_hook', {}));
  await assert.rejects(h.call(undefined));
  denied(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) }));
});

async function client(t, f, capabilities = {}) {
  const child = spawn(process.execPath, [new URL('../adapters/mcp.mjs', import.meta.url).pathname, f.configPath], { stdio: ['pipe', 'pipe', 'pipe'] });
  const exited = once(child, 'exit');
  t.after(async () => { child.stdin.end(); if (child.exitCode === null) child.kill(); await exited; });
  let id = 0; const pending = new Map(), elicited = [];
  const lines = createInterface({ input: child.stdout });
  lines.on('line', line => { const data = JSON.parse(line); if (data.method) elicited.push(data); else pending.get(data.id)?.(data); });
  const send = value => child.stdin.write(JSON.stringify({ jsonrpc: '2.0', ...value }) + '\n');
  const request = (method, params) => new Promise((resolve, reject) => {
    const key = ++id; const timer = setTimeout(() => reject(new Error('MCP test response timeout')), 10000);
    pending.set(key, data => { clearTimeout(timer); pending.delete(key); resolve(data); }); send({ id: key, method, params });
  });
  assert.equal((await request('initialize', { protocolVersion: '2025-06-18', capabilities, clientInfo: { name: 'fixture', version: '1' } })).result.serverInfo.name, 'sage-kit-local');
  const call = async (name, args = {}) => (await request('tools/call', { name, arguments: args })).result;
  return { child, exited, call, request, send, elicited, get lastId() { return id; } };
}

test('real stdio transport initializes, calls tools, rejects unknown args and closes on EOF', async t => {
  const f = await fixture(t), c = await client(t, f);
  assert.equal((await c.request('tools/list')).result.tools.length, 4);
  assert.equal((await c.call('sage_inspect')).structuredContent.action, 'continue');
  assert.equal((await c.call('sage_begin', { stepId: 'one', attemptId: 'first', approve: true })).isError, true);
  c.child.stdin.end(); await c.exited; assert.equal(c.child.exitCode, 0);
});

test('transport closes on overlong input instead of retaining an unbounded line', async t => {
  const f = await fixture(t), c = await client(t, f);
  c.child.stdin.on('error', () => {});
  c.child.stdin.write('x'.repeat(1024 * 1024 + 1));
  await c.exited; assert.equal(c.child.exitCode, 0);
});

test('config reads have a hard actual byte cap', async t => {
  const f = await fixture(t); await f.put('config.json', ' '.repeat(65537));
  await assert.rejects(readConfig(f.configPath), /64 KiB/);
});

for (const response of ['unsupported', 'decline', 'accept', 'cancel', 'invalid-response', 'notification']) {
  test(`RSI transport ${response} is bound to host elicitation, never model arguments`, { skip: process.platform === 'win32', timeout: 20000 }, async t => {
    const f = await fixture(t, { rsiPlanPath: 'rsi-plan.json', rsiStatePath: 'rsi-state.json' });
    await f.put('strategy.txt', 'BAD'); await f.put('feedback.txt', 'Fixed evaluator observed BAD');
    await f.put('eval.mjs', "import{readFileSync}from'node:fs';process.exitCode=readFileSync('strategy.txt','utf8')==='GOOD'?0:1;");
    await f.put('rsi-plan.json', { version: 1, authority: ['SPEC.md'], inputs: ['strategy.txt', 'eval.mjs'], targets: ['strategy.txt'], command: [process.execPath, 'eval.mjs'], expiresAt: '2099-01-01T00:00:00Z', revoked: false, maxEvaluations: 1, timeoutMs: 2000, maxOutputBytes: 4096 });
    const c = await client(t, f, response === 'unsupported' ? {} : { elicitation: {} });
    assert.notEqual((await c.call('sage_rsi_propose', { hypothesis: 'Repair observed failure', feedback: [{ path: 'feedback.txt', kind: 'failure' }], files: [{ path: 'strategy.txt', content: 'GOOD' }] })).isError, true);
    assert.equal((await c.call('sage_rsi_evaluate')).structuredContent.evaluation.eligible, true);
    assert.equal((await c.call('sage_rsi_adopt', { approve: true })).isError, true);
    const adopting = c.call('sage_rsi_adopt');
    if (response !== 'unsupported') {
      for (let n = 0; n < 100 && !c.elicited.length; n++) await delay(10);
      assert.equal(c.elicited.length, 1);
      const e = c.elicited[0]; assert.equal(e.method, 'elicitation/create'); assert.match(e.params.message, /"before":"BAD","after":"GOOD"/);
      if (response === 'notification') c.send({ method: 'notifications/cancelled', params: { requestId: c.lastId } });
      c.send({ id: e.id, result: { action: ['invalid-response', 'notification'].includes(response) ? 'accept' : response, ...(['accept', 'invalid-response', 'notification'].includes(response) ? { content: { approve: true } } : {}) }, ...(response === 'invalid-response' ? { error: { code: -32600, message: 'Malformed approval response' } } : {}) });
    }
    const result = await adopting;
    assert.equal(result.isError === true, response !== 'accept');
    assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), response === 'accept' ? 'GOOD' : 'BAD');
  });
}
