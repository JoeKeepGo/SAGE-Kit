// Optional in-host adapter. No shell, model, network, polling or history store.
import { realpath } from 'node:fs/promises';
import { isAbsolute, relative } from 'node:path';
import { createHash } from 'node:crypto';
import Schema from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { openContinuation } from './continuation.mjs';

export const name = 'sage-kit-dsh';
export const inject = ['tools'];
export const Config = Schema.object({
  projectRoot: Schema.string().required(),
  planPath: Schema.string().required(),
  statePath: Schema.string().required(),
  guardedTools: Schema.array(Schema.string()).default([]),
  deadlineMs: Schema.number().default(2000),
  maxContextBytes: Schema.number().default(16384),
  remindEverySteps: Schema.number().default(8),
});
const error = (code, message) => Object.assign(new Error(message), { code });
const digest = value => createHash('sha256').update(value).digest('hex');
const stopped = new Set(['revoked', 'expired', 'authority_changed', 'evidence_changed']);

export async function apply(ctx, config) {
  if (!isAbsolute(config.projectRoot)) throw error('E_CONFIG', 'projectRoot must be absolute');
  for (const [key, min, max] of [['deadlineMs', 100, 10000], ['maxContextBytes', 1024, 65536], ['remindEverySteps', 1, 100]]) {
    if (!Number.isInteger(config[key]) || config[key] < min || config[key] > max) throw error('E_CONFIG', `Invalid ${key}`);
  }
  if (config.guardedTools.length > 100 || config.guardedTools.some(n => !/^[a-zA-Z0-9_-]{1,100}$/.test(n) || n.startsWith('sage_'))) {
    throw error('E_CONFIG', 'Invalid guardedTools');
  }
  const root = await realpath(config.projectRoot);
  const controller = await openContinuation({ root, planPath: config.planPath, statePath: config.statePath });
  const sessions = new WeakMap();
  const guarded = new Set(config.guardedTools);
  const memory = agent => {
    if (!agent?.session) throw error('E_SESSION', 'Governance requires an Agent session');
    if (!sessions.has(agent.session)) sessions.set(agent.session, {});
    return sessions.get(agent.session);
  };
  const cwdOf = agent => ctx.get('workingDirectory')?.get(agent.session) ?? agent.session.header.cwd;
  async function inProject(agent, signal) {
    signal.throwIfAborted();
    const cwd = cwdOf(agent);
    if (typeof cwd !== 'string' || !isAbsolute(cwd)) throw error('E_PROJECT', 'Agent cwd is unavailable');
    const path = relative(root, await realpath(cwd));
    signal.throwIfAborted();
    return { inside: path === '' || (!path.startsWith('..' + '/') && path !== '..' && !isAbsolute(path) && !path.startsWith('..\\')), cwd };
  }
  function diagnostic(value) {
    // Observers cannot authorize work, alter a result or force persistent logs.
    try { ctx.emit('sage/diagnostic', value); } catch { /* diagnostics are advisory */ }
  }
  async function operation(operation, signal, fn) {
    const began = performance.now();
    try {
      signal.throwIfAborted();
      const value = await fn({ signal });
      diagnostic({ operation, elapsedMs: performance.now() - began, ...(value.io ? { io: value.io } : {}) });
      return value;
    } catch (cause) {
      diagnostic({ operation, elapsedMs: performance.now() - began, code: cause.code ?? cause.name ?? 'E_GOVERNANCE' });
      throw cause;
    }
  }
  const deadline = parent => AbortSignal.any([...(parent ? [parent] : []), AbortSignal.timeout(config.deadlineMs)]);
  function save(data, value) {
    data.decision = value;
    data.active = value.action === 'reconcile' ? value.attempt : undefined;
    data.blocked = stopped.has(value.action);
    if (!data.active || data.owner !== data.active.id) data.owner = undefined;
    data.dirty = false;
  }
  function render(data) {
    const value = data.decision;
    const action = data.active && data.owner === data.active.id ? 'working' : value.action;
    const content = JSON.stringify({ action, ...value.context, ...(value.attempt ? { attempt: value.attempt } : {}) });
    const text = 'SAGE-Kit governance reminder. Project authority remains normative; execution records are observations, not approval. '
      + 'Read the referenced rules. Use sage_begin before the next admitted task; replayed begins must not repeat side effects. '
      + 'On reconcile, inspect actual effects and record their result before continuing. Required checks and review must be real. '
      + 'Completion awaits human acceptance; do not expand scope, publish, or adopt RSI candidates without authority.\n' + content;
    if (Buffer.byteLength(text) > config.maxContextBytes) throw error('E_CONTEXT_BUDGET', 'Governance context exceeds the configured budget');
    return text;
  }
  ctx.on('agent/pre-step', async (payload, next) => {
    const downstream = await next();
    if (downstream.kind === 'reject') return downstream;
    const data = memory(payload.agent);
    const signal = deadline(payload.signal);
    try {
      const project = await inProject(payload.agent, signal);
      if (!project.inside) { data.owner = undefined; data.blocked = true; return downstream; }
      data.cwd = project.cwd;
      const generation = payload.agent.session.surface.replaceGeneration;
      const boundary = !data.decision || data.turn !== payload.turn || data.generation !== generation;
      if (boundary || data.dirty) {
        save(data, await operation('inspect', signal, opts => controller.inspect(opts)));
      } else {
        const seen = await operation('observe', signal, opts => controller.observe(opts));
        if (seen.revision !== data.decision.revision || seen.fingerprint !== data.decision.fingerprint || stopped.has(seen.status)) {
          save(data, await operation('inspect', signal, opts => controller.inspect(opts)));
        }
      }
      if (data.blocked) { data.owner = undefined; return { kind: 'reject' }; }
      const text = render(data);
      const key = digest(text);
      const remind = boundary || key !== data.injectedKey || payload.step - data.injectedStep >= config.remindEverySteps;
      data.turn = payload.turn;
      data.generation = generation;
      if (!remind) return downstream;
      signal.throwIfAborted();
      const message = createUserMessage({ content: [{ type: 'text', text }], source: { kind: 'sage-kit' } });
      const lastClaimed = downstream.messages.findLastIndex(m => payload.messages.includes(m));
      data.injectedKey = key;
      data.injectedStep = payload.step;
      diagnostic({ operation: 'inject', bytes: Buffer.byteLength(text) });
      return { ...downstream, messages: downstream.messages.toSpliced(lastClaimed < 0 ? downstream.messages.length : lastClaimed + 1, 0, message) };
    } catch (cause) {
      data.blocked = true;
      data.owner = undefined;
      diagnostic({ operation: 'pre-step-error', code: cause.code ?? cause.name ?? 'E_GOVERNANCE' });
      ctx.logger?.warn?.(`sage-kit: governance unavailable (${cause.code ?? cause.name ?? 'E_GOVERNANCE'}); reconcile before retrying`);
      return { kind: 'reject' };
    }
  });

  ctx.on('tools/pre-execute', async (exec, next) => {
    const downstream = await next();
    if (!guarded.has(exec.name) || ['deny', 'cancel'].includes(downstream.kind)) return downstream;
    try {
      exec.signal.throwIfAborted();
      const data = memory(exec.agent);
      // The model step owns the fresh bounded read; sibling tools do no disk IO.
      if (!data.blocked && data.cwd === cwdOf(exec.agent) && data.owner && data.active?.id === data.owner &&
          Date.now() < Date.parse(data.decision.context.expiresAt)) return downstream;
    } catch { /* missing/cancelled context never grants execution */ }
    return { kind: 'deny', reason: 'SAGE-Kit requires a fresh admitted intent owned by this session; reconcile rather than replay effects' };
  });
  function register(toolName, parameters, description, run) {
    ctx.tools.register(defineTool({
      name: toolName, parameters, description, timeoutMs: config.deadlineMs,
      isConcurrencySafe: () => false,
      output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
      async execute(args, exec) {
        const signal = deadline(exec.signal);
        const data = memory(exec.agent);
        try {
          if (!(await inProject(exec.agent, signal)).inside) throw error('E_PROJECT', 'Agent is outside the configured project');
          const result = await operation(toolName, signal, opts => run(args, data, opts));
          return JSON.stringify(result);
        } catch (cause) {
          data.owner = undefined;
          data.active = undefined;
          data.blocked = true;
          data.dirty = true;
          throw cause;
        }
      },
    }));
  }
  register('sage_inspect', {}, 'Read current governance and fully verify evidence before proposing the next task.', async (_args, data, opts) => {
    const value = await controller.inspect(opts);
    save(data, value);
    return value;
  });
  register('sage_begin', { stepId: { type: 'string', required: true }, attemptId: { type: 'string', required: true } },
    'Persist intent for an admitted task. A replay never authorizes repeating its side effects.', async (args, data, opts) => {
      const value = await controller.begin(args.stepId, args.attemptId, opts);
      data.owner = value.replayed ? undefined : value.attempt.id;
      data.active = value.replayed ? undefined : value.attempt;
      data.dirty = true;
      return value;
    });
  register('sage_finish', { attemptId: { type: 'string', required: true }, result: { type: 'string', required: true } },
    'Record a checked result or reconciled outcome. result is JSON with outcome, checks, and required review evidence.', async (args, data, opts) => {
      if (Buffer.byteLength(args.result) > 65536) throw error('E_RESULT_BUDGET', 'Result input exceeds 64 KiB');
      const value = await controller.finish(args.attemptId, JSON.parse(args.result), opts);
      data.owner = undefined;
      data.active = undefined;
      data.dirty = true;
      return value;
    });
}
