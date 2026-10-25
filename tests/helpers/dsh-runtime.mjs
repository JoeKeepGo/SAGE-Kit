// Real DSH components with a deterministic, in-process model double. No profile
// loader, provider adapter, credential file or network transport is installed.
import assert from 'node:assert/strict';
import { cp, mkdtemp, readFile, rm, symlink } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';

export const dshAvailable = Boolean(process.env.SAGE_DSH_NODE_MODULES);
export const dshSkipReason = 'Set SAGE_DSH_NODE_MODULES to the existing DSH 0.2.1-rc.2 node_modules; no host installation is performed by this test.';

export async function createDshRuntime(t, config, { approvalPolicy } = {}) {
  assert.ok(dshAvailable, dshSkipReason);
  const modules = resolve(process.env.SAGE_DSH_NODE_MODULES);
  const serviceNames = ['dsh-agent', 'dsh-session', 'dsh-session-projection', 'dsh-llm', 'dsh-system-prompt', 'dsh-tools', 'dsh-agent-loop'];
  if (approvalPolicy !== undefined) serviceNames.push('dsh-user-approval');
  for (const name of serviceNames) {
    const pkg = JSON.parse(await readFile(join(modules, '@deepseek-ai', name, 'package.json'), 'utf8'));
    assert.equal(pkg.version, '0.2.1-rc.2', `${name}: this evidence is version-specific`);
  }
  const load = name => import(pathToFileURL(join(modules, '@deepseek-ai', name, 'lib/index.js')));
  const { Context } = await load('cordis');
  const { createUserMessage } = await load('dsh-llm');
  const { defineTool } = await load('dsh-tools');
  const ctx = new Context();
  const stage = await mkdtemp(join(tmpdir(), 'sage-dsh-package-'));
  const agents = [];
  let disposed = false;
  const dispose = async () => {
    if (disposed) return;
    disposed = true;
    for (const agent of agents) agent.cancel({ kind: 'user' });
    await ctx.fiber.dispose();
    await rm(stage, { recursive: true, force: true });
  };
  t.after(dispose);
  const pluginPath = process.env.SAGE_DSH_PLUGIN_PATH
    ? resolve(process.env.SAGE_DSH_PLUGIN_PATH) : join(stage, 'adapters', 'dsh.mjs');
  if (!process.env.SAGE_DSH_PLUGIN_PATH) {
    await cp(new URL('../../adapters/', import.meta.url), join(stage, 'adapters'), { recursive: true });
    await symlink(modules, join(stage, 'node_modules'), process.platform === 'win32' ? 'junction' : 'dir');
  }
  for (const name of serviceNames) {
    const { default: Service } = await load(name);
    const options = name === 'dsh-system-prompt' ? { includeHarnessIdentity: false, includeRuntimeContext: false }
      : name === 'dsh-tools' ? { mode: 'native' }
      : name === 'dsh-agent-loop' ? { agents: [], maxParallelToolCalls: 1 }
      : name === 'dsh-user-approval' ? { policy: approvalPolicy } : undefined;
    await ctx.plugin(Service, options);
  }
  const requests = [], events = [], errors = [], diagnostics = [];
  ctx.on('sage/diagnostic', event => diagnostics.push(event));
  ctx.on('agent/error', ({ agent, error }) => errors.push({ agentId: agent.id, error }));
  ctx.on('session/event', (session, event) => events.push({ sessionId: session.id, ...event }));
  let scripted = [], callNumber = 0;
  ctx.on('llm/stream', options => {
    requests.push({ provider: options.provider, model: options.model, messages: structuredClone(options.messages), tools: structuredClone(options.tools) });
    const action = scripted.shift();
    return (async function* () {
      options.signal?.throwIfAborted();
      const response = typeof action === 'function' ? await action(options) : action;
      if (response?.tool || response?.tools) {
        const calls = response.tools ?? [response];
        for (const [index, call] of calls.entries()) {
          yield { type: 'tool-call-delta', index, id: `fixture-${++callNumber}`, name: call.tool, argumentsDelta: JSON.stringify(call.args ?? {}) };
        }
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
      } else {
        yield { type: 'text-delta', index: 0, text: 'Deterministic fixture turn completed.' };
        yield { type: 'finish', reason: { kind: 'stop' } };
      }
    })();
  });
  const plugin = await import(pathToFileURL(pluginPath));
  await ctx.plugin(plugin, config);
  const createAgent = async () => {
    const agent = await ctx.agentLoop.create(`fixture-${agents.length + 1}`, { provider: 'local-fixture', model: 'deterministic' }, { cwd: config.projectRoot });
    agents.push(agent);
    return agent;
  };
  const register = (name, execute, parameters = {}) => ctx.tools.register(defineTool({
    name, description: `Local test fixture ${name}`, parameters,
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    execute,
  }));
  const run = async (agent, actions = []) => {
    scripted = [...actions];
    const start = { requests: requests.length, events: events.length, errors: errors.length, diagnostics: diagnostics.length };
    let timer;
    try {
      agent.followup(createUserMessage({ content: [{ type: 'text', text: 'Continue the admitted fixture work.' }], source: { kind: 'user' } }));
      await Promise.race([agent.whenIdle(), new Promise((_, reject) => {
        timer = setTimeout(() => { agent.cancel({ kind: 'user' }); reject(new Error('DSH fixture turn exceeded 8 seconds')); }, 8000);
      })]);
    } finally { clearTimeout(timer); }
    return { requests: requests.slice(start.requests), events: events.slice(start.events), errors: errors.slice(start.errors), diagnostics: diagnostics.slice(start.diagnostics), unusedActions: scripted.length };
  };
  const replaceGovernance = agent => {
    const previous = events.findLast(event => event.sessionId === agent.session.id && event.type === 'user/message' && event.data.source?.kind === 'sage-kit');
    assert.ok(previous, 'a real governance surface node must exist before replacement');
    const generation = agent.session.surface.replaceGeneration;
    agent.session.append('user/message', createUserMessage({ content: [{ type: 'text', text: 'Fixture summary replaces the earlier governance message.' }], source: { kind: 'fixture-summary' } }), {
      surfaceOp: { op: 'replace', startSeq: previous.seq, endSeq: previous.seq }, sourceEventSeqs: [previous.seq],
    });
    assert.equal(agent.session.surface.replaceGeneration, generation + 1);
    return previous;
  };
  return { ctx, requests, events, errors, diagnostics, createAgent, register, run, replaceGovernance, dispose };
}

export const toolResults = run => run.events.filter(event => event.type === 'tool/result').map(event => event.data);
export const toolResultText = result => result.message.content.filter(block => block.type === 'text').map(block => block.text).join('\n');
export const governanceMessages = run => run.events.filter(event => event.type === 'user/message' && event.data.source?.kind === 'sage-kit');
