import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm, stat, cp, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawn, execFile } from 'node:child_process';
import { once } from 'node:events';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
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

async function client(t, f, capabilities = {}, entry = new URL('../adapters/mcp.mjs', import.meta.url).pathname) {
  const child = spawn(process.execPath, [entry, f.configPath], { stdio: ['pipe', 'pipe', 'pipe'] });
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
  const { serverInfo } = (await request('initialize', { protocolVersion: '2025-06-18', capabilities, clientInfo: { name: 'fixture', version: '1' } })).result;
  assert.equal(serverInfo.name, 'sage-kit-local');
  const call = async (name, args = {}) => (await request('tools/call', { name, arguments: args })).result;
  return { child, exited, call, request, send, elicited, serverInfo, get lastId() { return id; } };
}

test('stdio identity uses metadata beside the loaded module, independent of cwd and source version', async t => {
  const f = await fixture(t), directory = join(f.root, 'adapter');
  await cp(new URL('../adapters/', import.meta.url), directory, { recursive: true });
  const metadata = JSON.parse(await readFile(join(directory, 'package.json'), 'utf8'));
  metadata.version = '0.0.0-identity-regression';
  await writeFile(join(directory, 'package.json'), JSON.stringify(metadata));
  const c = await client(t, f, {}, join(directory, 'mcp.mjs'));
  assert.equal(c.serverInfo.version, metadata.version);
});

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

test('stdio publishes the finish evidence contract and accepts it without relaxing failed or missing evidence', async t => {
  const f = await fixture(t), c = await client(t, f);
  const definition = (await c.request('tools/list')).result.tools.find(tool => tool.name === 'sage_finish');
  const contract = definition.inputSchema.properties.result;
  assert.deepEqual(contract.required, ['outcome', 'checks']);
  assert.deepEqual(contract.properties.outcome.enum, ['passed', 'failed', 'not_executed']);
  assert.deepEqual(contract.properties.checks.items.required, ['id', 'passed', 'evidence']);
  assert.equal(contract.properties.review.type, 'string');
  await c.call('sage_begin', { stepId: 'one', attemptId: 'first' });
  const check = { id: 'check', passed: true, evidence: 'check.txt' };
  assert.equal((await c.call('sage_finish', { attemptId: 'first', result: { outcome: 'passed', checks: [check] } })).isError, true, 'missing file stays refused');
  await f.put('check.txt', 'Actual fixture check observation');
  assert.equal((await c.call('sage_finish', { attemptId: 'first', result: { outcome: 'passed', checks: [{ ...check, passed: false }] } })).isError, true, 'failed check cannot pass');
  const oldShape = { outcome: 'passed', checks: [{ id: 'check', passed: true, logPath: 'check.txt' }] };
  assert.equal((await c.call('sage_finish', { attemptId: 'first', result: oldShape })).isError, true, 'trial failure shape stays refused');
  assert.notEqual((await c.call('sage_finish', { attemptId: 'first', result: { outcome: 'passed', checks: [check] } })).isError, true);
  assert.equal((await c.call('sage_inspect')).structuredContent.action, 'human_gate');
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
    assert.ok(!(await c.request('tools/list')).result.tools.some(tool => tool.name === 'sage_rsi_observe'), 'manual mode must not expose automatic observation');
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


async function automaticFixture(t, { postFailure = false, target = 'strategy.txt' } = {}) {
  const f = await fixture(t, { rsiPlanPath: 'rsi-plan.json', rsiStatePath: 'rsi-state.json' });
  await mkdir(join(f.root, '.claude'), { recursive: true });
  await f.put(target, 'BAD');
  const marker = join(f.root, 'regression.flag');
  await f.put('eval.mjs', `import{readFileSync,existsSync}from'node:fs';const good=readFileSync(${JSON.stringify(target)},'utf8')==='GOOD';process.exitCode=good&&!existsSync(${JSON.stringify(marker)})&&!(${postFailure}&&process.cwd()===${JSON.stringify(f.root)})?0:1;`);
  let failure;
  try { await promisify(execFile)(process.execPath, ['eval.mjs'], { cwd: f.root, timeout: 3000, maxBuffer: 4096 }); }
  catch (cause) { failure = cause; }
  assert.equal(failure?.code, 1, 'the original fixed check must really fail');
  await f.put('feedback.txt', 'Fixed original evaluator exit 1.\n' + (failure.stdout ?? '') + (failure.stderr ?? ''));
  await f.put('rsi-plan.json', { version: 1, authority: ['SPEC.md'], inputs: [target, 'eval.mjs'], targets: [target], command: [process.execPath, 'eval.mjs'], expiresAt: '2099-01-01T00:00:00Z', revoked: false, maxEvaluations: 2, timeoutMs: 2000, maxOutputBytes: 4096 });
  f.config.rsiAutomaticPolicy = { branch: 'workflow/auto-fixture', baseBranch: 'main', planSha256: createHash('sha256').update(await readFile(join(f.root, 'rsi-plan.json'))).digest('hex'), maxRounds: 2, improvement: { kind: 'repair' } };
  await f.put('config.json', f.config);
  await f.put('.gitignore', 'state.json*\nrsi-state.json*\nregression.flag\n');
  const git = args => promisify(execFile)('git', args, { cwd: f.root, env: { PATH: '/usr/bin:/bin', HOME: f.root, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' }, timeout: 3000, maxBuffer: 65536 });
  await git(['init', '-b', 'main']); await git(['add', '.']);
  await git(['-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid', '-c', 'core.hooksPath=/dev/null', 'commit', '--no-gpg-sign', '-m', 'Isolated acceptance baseline']);
  await git(['checkout', '-b', 'workflow/auto-fixture']);
  const proposal = { hypothesis: 'Repair observed failure within preauthorized branch', feedback: [{ path: 'feedback.txt', kind: 'failure' }], files: [{ path: target, content: 'GOOD' }] };
  return { ...f, proposal, target };
}

for (const recovery of ['observe', 'rollback']) test(`automatic RSI real stdio adopts without elicitation and ${recovery} restores the original`, { skip: process.platform === 'win32', timeout: 20000 }, async t => {
  const f = await automaticFixture(t), c = await client(t, f);
  const tools = (await c.request('tools/list')).result.tools;
  assert.ok(tools.some(tool => tool.name === 'sage_rsi_observe'));
  assert.ok(!tools.some(tool => tool.name === 'sage_rsi_adopt'));
  assert.match(tools.find(tool => tool.name === 'sage_rsi_evaluate').description, /preauthorized|pre-authorized/);
  assert.equal((await c.call('sage_rsi_propose', { ...f.proposal, rsiAutomaticPolicy: f.config.rsiAutomaticPolicy })).isError, true);
  assert.notEqual((await c.call('sage_rsi_propose', f.proposal)).isError, true);
  const adopted = await c.call('sage_rsi_evaluate');
  assert.notEqual(adopted.isError, true, JSON.stringify(adopted));
  assert.equal(adopted.structuredContent.status, 'adopted');
  assert.equal(await readFile(join(f.root, f.target), 'utf8'), 'GOOD');
  assert.equal(c.elicited.length, 0);
  if (recovery === 'observe') await f.put('regression.flag', 'Observed external regression');
  const observed = await c.call(`sage_rsi_${recovery}`);
  assert.notEqual(observed.isError, true, JSON.stringify(observed));
  assert.equal(observed.structuredContent.status, 'rolled_back');
  assert.equal(await readFile(join(f.root, f.target), 'utf8'), 'BAD');
  assert.equal(c.elicited.length, 0, 'preauthorization must never be represented as a human response');
});

test('automatic RSI failing actual-project postcheck restores the original without a human service', { skip: process.platform === 'win32', timeout: 20000 }, async t => {
  const f = await automaticFixture(t, { postFailure: true }), h = await openAgentHost(f.config, { configPath: f.configPath, authorize: () => assert.fail('automatic mode must not call human approval') });
  await h.call('sage_rsi_propose', f.proposal);
  const result = await h.call('sage_rsi_evaluate');
  assert.equal(result.status, 'rolled_back');
  assert.equal(await readFile(join(f.root, f.target), 'utf8'), 'BAD');
  await assert.rejects(h.call('sage_rsi_adopt'));
  assert.match((await h.call('sage_inspect')).reminder, /preauthorized|pre-authorized/);
});

for (const target of ['AGENTS.md', '.claude/settings.json', 'config.json']) {
  test(`automatic RSI cannot propose changing its protected host rules ${target}`, { skip: process.platform === 'win32', timeout: 10000 }, async t => {
    const f = await automaticFixture(t, { target }), h = await openAgentHost(f.config, { configPath: f.configPath });
    const before = await readFile(join(f.root, target));
    await assert.rejects(h.call('sage_rsi_propose', f.proposal));
    assert.deepEqual(await readFile(join(f.root, target)), before);
    await assert.rejects(readFile(join(f.root, 'rsi-state.json')), { code: 'ENOENT' });
  });
}


test('Codex canonical hook names match configured shell and patch API names without gating orchestration', async t => {
  const f = await fixture(t, { guardedTools: ['exec_command', 'apply_patch'] });
  const h = await openAgentHost(f.config);
  for (const name of ['Bash', 'apply_patch']) denied(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: name }) }));
  assert.deepEqual(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'exec' }) }), {});
  await begin(h);
  for (const name of ['Bash', 'apply_patch']) assert.deepEqual(await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: name }) }), {});
  const aliases = await openAgentHost({ ...f.config, guardedTools: ['shell_command', 'Edit'] });
  for (const name of ['Bash', 'apply_patch']) denied(await aliases.call('sage_hook', { event: f.event('PreToolUse', { tool_name: name }) }));
  const claude = await openAgentHost({ ...f.config, host: 'claude', guardedTools: ['Write'] });
  denied(await claude.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) }));
  assert.deepEqual(await claude.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'apply_patch' }) }), {});
});

test('PreToolUse failure emits only a native deny; unsupported continue:false must never discard the decision', async t => {
  const f = await fixture(t), h = await openAgentHost(f.config);
  await begin(h);
  await rm(join(f.root, 'SPEC.md'));
  const value = await h.call('sage_hook', { event: f.event('PreToolUse', { tool_name: 'Write' }) });
  assert.deepEqual(Object.keys(value), ['hookSpecificOutput']);
  assert.equal(value.hookSpecificOutput.hookEventName, 'PreToolUse');
  denied(value);
  assert.match(value.hookSpecificOutput.permissionDecisionReason, /governance unavailable/);
  const malformed = await h.call('sage_hook', {});
  assert.deepEqual(Object.keys(malformed), ['hookSpecificOutput']);
  denied(malformed);
});

for (const automatic of [false, true]) {
  test(`RSI proposal stdio contract exposes nested objects in ${automatic ? 'automatic' : 'manual'} mode and preserves validation`, { skip: process.platform === 'win32', timeout: 10000 }, async t => {
    const f = automatic ? await automaticFixture(t) : await fixture(t, { rsiPlanPath: 'rsi-plan.json', rsiStatePath: 'rsi-state.json' });
    if (!automatic) {
      await f.put('strategy.txt', 'BAD'); await f.put('feedback.txt', 'Existing failure evidence');
      await f.put('eval.mjs', 'process.exitCode = 1;');
      await f.put('rsi-plan.json', { version: 1, authority: ['SPEC.md'], inputs: ['strategy.txt', 'eval.mjs'], targets: ['strategy.txt'], command: [process.execPath, 'eval.mjs'], expiresAt: '2099-01-01T00:00:00Z', revoked: false, maxEvaluations: 1, timeoutMs: 2000, maxOutputBytes: 4096 });
    }
    const c = await client(t, f);
    const tools = (await c.request('tools/list')).result.tools;
    const definition = tools.find(tool => tool.name === 'sage_rsi_propose');
    const contract = definition.inputSchema;
    assert.deepEqual(contract.required, ['hypothesis', 'feedback', 'files']);
    assert.equal(contract.properties.hypothesis.maxLength, 4096);
    assert.ok(new RegExp(contract.properties.hypothesis.pattern).test('Actual observed failure'));
    assert.ok(!new RegExp(contract.properties.hypothesis.pattern).test('  \t\n'));
    for (const name of ['feedback', 'files']) {
      assert.equal(contract.properties[name].type, 'array');
      assert.equal(contract.properties[name].minItems, 1);
      assert.equal(contract.properties[name].maxItems, 20);
      assert.equal(contract.properties[name].items.type, 'object');
      assert.equal(contract.properties[name].items.properties.path.type, 'string');
      assert.equal(contract.properties[name].items.properties.path.maxLength, 4096);
    }
    assert.deepEqual(contract.properties.feedback.items.required, ['path', 'kind']);
    assert.deepEqual(contract.properties.feedback.items.properties.kind.enum, ['failure', 'review', 'rework']);
    assert.deepEqual(contract.properties.files.items.required, ['path', 'content']);
    assert.deepEqual(contract.properties.files.items.properties.content.type, ['string', 'null']);
    assert.match(contract.properties.files.description, /262144 UTF-8 bytes/);
    assert.match(definition.description, /feedback:\[\{path,kind\}\].*files:\[\{path,content\}\]/);
    assert.match(definition.description, /does not adopt/);
    if (automatic) {
      assert.match(definition.description, /preauthorized/);
      assert.ok(!tools.some(tool => tool.name === 'sage_rsi_adopt'));
      assert.ok(tools.some(tool => tool.name === 'sage_rsi_observe'));
      assert.match(tools.find(tool => tool.name === 'sage_rsi_evaluate').description, /No per-candidate human approval/);
    } else {
      assert.match(definition.description, /separate human response/);
      assert.ok(tools.some(tool => tool.name === 'sage_rsi_adopt'));
      assert.ok(!tools.some(tool => tool.name === 'sage_rsi_observe'));
      assert.match(tools.find(tool => tool.name === 'sage_rsi_evaluate').description, /manual mode does not adopt/);
    }
    const valid = { hypothesis: 'Repair actual observed failure', feedback: [{ path: 'feedback.txt', kind: 'failure' }], files: [{ path: 'strategy.txt', content: automatic ? 'GOOD' : null }] };
    for (const invalid of [
      { ...valid, feedback: ['feedback.txt'] },
      { ...valid, files: [JSON.stringify(valid.files[0])] },
      { ...valid, feedback: [{ path: 'feedback.txt', kind: 'approve' }] },
      { ...valid, files: [{ path: 'strategy.txt' }] },
      { ...valid, feedback: [{ path: 'missing.txt', kind: 'failure' }] },
      { ...valid, files: [{ path: 'SPEC.md', content: 'Changed authority' }] },
      { ...valid, rsiAutomaticPolicy: { branch: 'model-supplied' } },
    ]) assert.equal((await c.call('sage_rsi_propose', invalid)).isError, true, JSON.stringify(invalid));
    const accepted = await c.call('sage_rsi_propose', valid);
    assert.notEqual(accepted.isError, true, JSON.stringify(accepted));
    assert.equal(accepted.structuredContent.status, 'proposed');
    assert.equal(accepted.structuredContent.proposal.files[0].content, valid.files[0].content);
    assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD', 'propose alone must never adopt or delete');
    assert.equal(c.elicited.length, 0, 'propose is not an approval operation');
  });
}
