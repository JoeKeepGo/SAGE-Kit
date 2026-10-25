import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runClaude } from './helpers/claude-host.mjs';
const binary = process.env.SAGE_CLAUDE_BINARY;
const adapterDir = process.env.SAGE_AGENT_ADAPTER_DIR ? resolve(process.env.SAGE_AGENT_ADAPTER_DIR) : fileURLToPath(new URL('../adapters/', import.meta.url));
const options = { timeout: 35000, skip: !binary && 'set SAGE_CLAUDE_BINARY to an installed official native Claude Code binary' };
async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'sage-claude-host-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const cwd = join(root, 'project'), home = join(root, 'home');
  await mkdir(cwd);
  return { cwd, home };
}

test('native Claude SessionStart injects context and native Write runs after PreToolUse', options, async t => {
  const { cwd, home } = await fixture(t);
  const hook = join(cwd, 'hook.mjs');
  await writeFile(hook, `import {appendFileSync} from 'node:fs';let s='';for await(const c of process.stdin)s+=c;const e=JSON.parse(s);appendFileSync('hook-events.jsonl',JSON.stringify(e)+'\\n');process.stdout.write(JSON.stringify({hookSpecificOutput:{hookEventName:e.hook_event_name,...(e.hook_event_name==='SessionStart'?{additionalContext:'SAGE_SESSION_AUTHORITY_MARKER'}:{permissionDecision:'allow'})}}));`);
  const handler = { type: 'command', command: process.execPath, args: [hook], timeout: 3 };
  const result = await runClaude({ binary, cwd, home, settings: { hooks: { SessionStart: [{ hooks: [handler] }], PreToolUse: [{ matcher: 'Write', hooks: [handler] }] } },
    responses: [[{ type: 'tool_use', id: 'tool_write1', name: 'Write', input: { file_path: join(cwd, 'actual.txt'), content: 'native side effect' } }]] });
  assert.equal(result.timedOut, false, result.stderr);
  assert.equal(result.code, 0, result.stderr + result.stdout);
  assert.ok(JSON.stringify(result.requests[0]).includes('SAGE_SESSION_AUTHORITY_MARKER'));
  assert.equal(await readFile(join(cwd, 'actual.txt'), 'utf8'), 'native side effect');
  const hooks = (await readFile(join(cwd, 'hook-events.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  assert.ok(hooks.some(e => e.hook_event_name === 'SessionStart' && e.source === 'startup'));
  assert.ok(hooks.some(e => e.hook_event_name === 'PreToolUse' && e.tool_name === 'Write'));
  t.diagnostic(JSON.stringify({ requests: result.requests.length, traffic: result.traffic, nativeInit: result.events.find(e => e.type === 'system' && e.subtype === 'init')?.claude_code_version }));
});

async function hookServer(cwd, mode) {
  const path = join(cwd, 'hook-server.mjs');
  await writeFile(path, `import {createInterface} from 'node:readline';import {appendFileSync} from 'node:fs';
for await(const line of createInterface({input:process.stdin})){
 const q=JSON.parse(line);if(!('id'in q))continue;let result;
 if(q.method==='initialize')result={protocolVersion:q.params.protocolVersion,capabilities:{tools:{}},serverInfo:{name:'fixture-hook',version:'1'}};
 else if(q.method==='tools/list')result={tools:[{name:'record_hook',description:'Local lifecycle fixture',inputSchema:{type:'object',properties:{event:{type:'object'}},required:['event']}}]};
 else if(q.method==='tools/call'){
  const e=q.params.arguments.event;appendFileSync('mcp-hooks.jsonl',JSON.stringify({pid:process.pid,event:e})+'\\n');
  const output={hookSpecificOutput:{hookEventName:e.hook_event_name,...(e.hook_event_name==='PreToolUse'?{permissionDecision:'deny',permissionDecisionReason:'FIXTURE_REQUIRED_BEGIN'}:{additionalContext:'SAGE_MCP_CURRENT_AUTHORITY'})}};
  result={content:[{type:'text',text:JSON.stringify(e.hook_event_name==='Stop'?{}:output)}],...(${JSON.stringify(mode)}==='error'&&e.hook_event_name==='PreToolUse'?{isError:true}:{})};
 }else result={};
 process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:q.id,result})+'\\n');
}`);
  return { command: process.execPath, args: [path] };
}

for (const mode of ['deny', 'error']) {
  test(`native MCP lifecycle hook ${mode === 'deny' ? 'injects and denies Write' : 'isError is fail-open despite its deny text'}`, options, async t => {
    const { cwd, home } = await fixture(t);
    const server = await hookServer(cwd, mode);
    const handler = { type: 'mcp_tool', server: 'fixture', tool: 'record_hook', timeout: 3,
      input: { event: { hook_event_name: '${hook_event_name}', session_id: '${session_id}', tool_name: '${tool_name}', tool_use_id: '${tool_use_id}', cwd: '${cwd}', source: '${source}', stop_hook_active: '${stop_hook_active}' } } };
    const result = await runClaude({ binary, cwd, home, mcpServers: { fixture: server }, settings: {
      permissions: { allow: ['Write'] },
      hooks: { SessionStart: [{ hooks: [handler] }], UserPromptSubmit: [{ hooks: [handler] }], PreToolUse: [{ matcher: 'Write', hooks: [handler] }], Stop: [{ hooks: [handler] }] },
    }, responses: [[{ type: 'tool_use', id: 'tool_write1', name: 'Write', input: { file_path: join(cwd, 'actual.txt'), content: 'native side effect' } }]] });
    assert.equal(result.timedOut, false, result.stderr);
    assert.equal(result.code, 0, result.stderr + result.stdout);
    assert.ok(JSON.stringify(result.requests[0]).includes('SAGE_MCP_CURRENT_AUTHORITY'));
    const hooks = (await readFile(join(cwd, 'mcp-hooks.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
    assert.equal(hooks.filter(x => x.event.hook_event_name === 'SessionStart').length, 0, 'launch SessionStart runs before MCP clients exist');
    assert.ok(hooks.some(x => x.event.hook_event_name === 'UserPromptSubmit'));
    const pre = hooks.find(x => x.event.hook_event_name === 'PreToolUse');
    assert.equal(pre.event.tool_name, 'Write');
    assert.equal(pre.event.tool_use_id, 'tool_write1');
    assert.equal(new Set(hooks.map(x => x.pid)).size, 1, 'lifecycle events reuse one connected server process');
    if (mode === 'deny') {
      await assert.rejects(stat(join(cwd, 'actual.txt')), { code: 'ENOENT' });
      assert.match(JSON.stringify(result.requests[1].messages), /FIXTURE_REQUIRED_BEGIN/);
    } else {
      assert.equal(await readFile(join(cwd, 'actual.txt'), 'utf8'), 'native side effect');
    }
    t.diagnostic(JSON.stringify({ mode, nativeMcp: result.events.find(e => e.type === 'system' && e.subtype === 'init')?.mcp_servers, hooks: hooks.map(x => x.event.hook_event_name), stopFlag: hooks.find(x => x.event.hook_event_name === 'Stop')?.event.stop_hook_active }));
  });
}

async function governed(t, { admitted = true, count = 1 } = {}) {
  const f = await fixture(t);
  await mkdir(join(f.cwd, 'output'));
  await writeFile(join(f.cwd, 'authority.md'), 'Preserve authority. Only approved steps may run. Human acceptance is separate.');
  const plan = { version: 1, goal: 'CLAUDE_REAL_CONTINUATION_GOAL', authority: ['authority.md'],
    constraints: ['No publication', 'No unapproved tasks'], maxAttempts: 10, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false,
    steps: Array.from({ length: count }, (_, i) => ({ id: `step${i + 1}`, objective: `Produce verified output ${i + 1}`,
      dependsOn: i ? [`step${i}`] : [], scope: ['output'], checks: ['test'], requiresReview: false, admitted, humanGate: false })) };
  await writeFile(join(f.cwd, 'plan.json'), JSON.stringify(plan));
  const config = join(f.cwd, 'sage-config.json');
  await writeFile(config, JSON.stringify({ host: 'claude', projectRoot: f.cwd, planPath: 'plan.json', statePath: 'state.json', guardedTools: ['Bash', 'Write', 'Edit'] }));
  const handler = { type: 'mcp_tool', server: 'sage', tool: 'sage_hook', timeout: 3, input: { event: {
    hook_event_name: '${hook_event_name}', session_id: '${session_id}', cwd: '${cwd}', source: '${source}', tool_name: '${tool_name}', tool_use_id: '${tool_use_id}',
  } } };
  return { ...f, plan, binary, settings: { permissions: { allow: ['mcp__sage__*', 'Bash', 'Write'] }, hooks: {
    SessionStart: [{ hooks: [{ type: 'command', command: process.execPath, args: [join(adapterDir, 'hook.mjs'), config], timeout: 3 }] }],
    UserPromptSubmit: [{ hooks: [handler] }], PreToolUse: [{ matcher: 'Bash|Write|Edit', hooks: [handler] }],
  } }, mcpServers: { sage: { command: process.execPath, args: [join(adapterDir, 'mcp.mjs'), config] } } };
}
const tool = (name, input, id) => [{ type: 'tool_use', id: `tool_${id}`, name: name.startsWith('sage_') ? `mcp__sage__${name}` : name, input }];
function toolResults(result) { return result.requests.flatMap(r => r.messages.flatMap(m => Array.isArray(m.content) ? m.content.filter(c => c.type === 'tool_result') : [])); }

test('native Claude uses installed SAGE MCP to deny early effects and finish three real checked steps', options, async t => {
  const f = await governed(t, { count: 3 });
  const responses = [tool('Write', { file_path: join(f.cwd, 'too-early.txt'), content: 'forbidden' }, 'early')];
  for (let i = 1; i <= 3; i++) {
    const command = `${process.execPath} -e 'const fs=require("node:fs");fs.writeFileSync("output/${i}.txt","verified-${i}");if(fs.readFileSync("output/${i}.txt","utf8")!=="verified-${i}")process.exit(4);fs.writeFileSync("output/${i}.check","actual command passed")'`;
    responses.push(tool('sage_begin', { stepId: `step${i}`, attemptId: `actual-${i}` }, `begin${i}`),
      tool('Bash', { command, timeout: 3000 }, `bash${i}`),
      tool('sage_finish', { attemptId: `actual-${i}`, result: { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: `output/${i}.check` }] } }, `finish${i}`));
  }
  responses.push(tool('sage_inspect', {}, 'inspect'));
  const result = await runClaude({ ...f, responses });
  assert.equal(result.timedOut, false, result.stderr);
  assert.equal(result.code, 0, result.stderr + result.stdout);
  assert.match(JSON.stringify(result.requests[0]), /CLAUDE_REAL_CONTINUATION_GOAL/);
  await assert.rejects(stat(join(f.cwd, 'too-early.txt')), { code: 'ENOENT' });
  const state = JSON.parse(await readFile(join(f.cwd, 'state.json'), 'utf8'));
  assert.equal(state.attempts.length, 3);
  assert.ok(state.attempts.every(a => a.outcome === 'passed'));
  for (let i = 1; i <= 3; i++) assert.equal(await readFile(join(f.cwd, `output/${i}.check`), 'utf8'), 'actual command passed');
  assert.match(JSON.stringify(toolResults(result).find(r => r.tool_use_id === 'tool_inspect')), /complete_pending_acceptance/);
  t.diagnostic(JSON.stringify({ nativeVersion: result.events.find(e => e.subtype === 'init')?.claude_code_version, requests: result.requests.length, adapterDir, checkedSteps: state.attempts.length }));
});

test('native SAGE rejects missing evidence and removes execution ownership before the next Write', options, async t => {
  const f = await governed(t);
  const result = await runClaude({ ...f, responses: [
    tool('sage_begin', { stepId: 'step1', attemptId: 'missing-evidence' }, 'begin'),
    tool('sage_finish', { attemptId: 'missing-evidence', result: { outcome: 'passed', checks: [{ id: 'test', passed: true, evidence: 'output/nonexistent.check' }] } }, 'finish'),
    tool('Write', { file_path: join(f.cwd, 'after-error.txt'), content: 'forbidden' }, 'write'),
    tool('sage_inspect', {}, 'inspect'),
  ] });
  assert.equal(result.code, 0, result.stderr + result.stdout);
  await assert.rejects(stat(join(f.cwd, 'after-error.txt')), { code: 'ENOENT' });
  const results = toolResults(result);
  assert.match(JSON.stringify(results.find(r => r.tool_use_id === 'tool_finish')), /ENOENT/);
  assert.match(JSON.stringify(results.find(r => r.tool_use_id === 'tool_inspect')), /reconcile/);
  const state = JSON.parse(await readFile(join(f.cwd, 'state.json'), 'utf8'));
  assert.equal(state.attempts[0].outcome, 'running');
});

test('native SAGE unadmitted begin cannot unlock a native write', options, async t => {
  const f = await governed(t, { admitted: false });
  const result = await runClaude({ ...f, responses: [
    tool('sage_begin', { stepId: 'step1', attemptId: 'not-admitted' }, 'begin'),
    tool('Write', { file_path: join(f.cwd, 'unadmitted.txt'), content: 'forbidden' }, 'write'),
  ] });
  assert.equal(result.code, 0, result.stderr + result.stdout);
  await assert.rejects(stat(join(f.cwd, 'unadmitted.txt')), { code: 'ENOENT' });
  await assert.rejects(stat(join(f.cwd, 'state.json')), { code: 'ENOENT' });
  assert.match(JSON.stringify(toolResults(result).find(r => r.tool_use_id === 'tool_begin')), /Cannot begin: blocked/);
});

test('native SAGE internal authority read failure returns a deny hook instead of a fail-open MCP error', options, async t => {
  const f = await governed(t);
  const result = await runClaude({ ...f, responses: [
    tool('sage_begin', { stepId: 'step1', attemptId: 'authority-failure' }, 'begin'),
    async () => { await rm(join(f.cwd, 'authority.md')); return tool('Write', { file_path: join(f.cwd, 'after-authority-error.txt'), content: 'forbidden' }, 'write'); },
  ] });
  assert.equal(result.code, 0, result.stderr + result.stdout);
  await assert.rejects(stat(join(f.cwd, 'after-authority-error.txt')), { code: 'ENOENT' });
  const denied = toolResults(result).find(r => r.tool_use_id === 'tool_write');
  // continue:false may stop the turn before a further model request carries
  // tool_result. Native hook events remain the attributable denial evidence.
  assert.match(JSON.stringify({ denied, events: result.events }), /governance unavailable.*ENOENT/);
  assert.equal(JSON.parse(await readFile(join(f.cwd, 'state.json'), 'utf8')).attempts[0].outcome, 'running');
});

test('native SAGE Stop maps string boolean substitution and requests at most one continuation', options, async t => {
  const f = await governed(t);
  const handler = { type: 'mcp_tool', server: 'sage', tool: 'sage_hook', timeout: 3, input: { event: {
    hook_event_name: '${hook_event_name}', session_id: '${session_id}', cwd: '${cwd}', stop_hook_active: '${stop_hook_active}',
  } } };
  f.settings.hooks.Stop = [{ hooks: [handler] }];
  const result = await runClaude({ ...f, responses: [[{ type: 'text', text: 'try to stop before admitted work' }], [{ type: 'text', text: 'handoff without claiming complete' }]] });
  assert.equal(result.code, 0, result.stderr + result.stdout);
  assert.equal(result.requests.length, 2, 'one Stop reminder, then host active flag prevents an endless completion loop');
  assert.match(JSON.stringify(result.requests[1].messages), /CLAUDE_REAL_CONTINUATION_GOAL/);
  await assert.rejects(stat(join(f.cwd, 'state.json')), { code: 'ENOENT' });
});
