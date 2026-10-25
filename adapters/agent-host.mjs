// Shared local host boundary. Transport/lifecycle failures never grant authority.
import { open, realpath } from 'node:fs/promises';
import { isAbsolute, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openContinuation } from './continuation.mjs';
import { openRSI } from './rsi.mjs';

const fail = (code, message) => { throw Object.assign(new Error(message), { code }); };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const inside = (root, path) => { const p = relative(root, path); return p === '' || (!isAbsolute(p) && p !== '..' && !p.startsWith('..' + sep)); };
const schema = (properties = {}, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false });
const string = { type: 'string' };
const definitions = [
  ['sage_inspect', 'Read current governance, next admitted work and reconciliation needs.', schema()],
  ['sage_begin', 'Record a new admitted attempt before effects. Replayed attempts MUST NOT repeat effects.', schema({ stepId: string, attemptId: string })],
  ['sage_finish', 'Record actual outcome with attributable evidence; never fabricate checks or human acceptance.', schema({ attemptId: string, result: { type: 'object' } })],
  ['sage_hook', 'Host lifecycle governance reminder/check. Does not grant permissions or run work.', schema({ event: { type: 'object' } })],
  ['sage_rsi_propose', 'Propose a candidate from actual feedback in configured targets.', schema({ hypothesis: string, feedback: { type: 'array' }, files: { type: 'array' } })],
  ...['inspect', 'evaluate', 'recover', 'adopt', 'rollback'].map(name => [`sage_rsi_${name}`, `Controlled RSI ${name}. Adopt/rollback require a separate human response through the host.`, schema()]),
];

export async function readConfig(path) {
  if (!isAbsolute(path)) fail('E_CONFIG', 'Config path must be absolute');
  const file = await open(path, 'r');
  try {
    // Bound actual reads, including a file which grows after stat.
    const bytes = Buffer.alloc(65537);
    let total = 0;
    while (total < bytes.length) {
      const { bytesRead } = await file.read(bytes, total, bytes.length - total, null);
      if (!bytesRead) break;
      total += bytesRead;
    }
    if (total > 65536) fail('E_CONFIG', 'Config exceeds 64 KiB');
    return JSON.parse(bytes.subarray(0, total).toString('utf8'));
  } finally { await file.close(); }
}

export async function openAgentHost(config, { configPath, authorize, diagnostic } = {}) {
  if (!object(config) || !['codex', 'claude'].includes(config.host) || !isAbsolute(config.projectRoot ?? '')) fail('E_CONFIG', 'Explicit host and absolute projectRoot required');
  const root = await realpath(config.projectRoot);
  const deadlineMs = config.deadlineMs ?? 2000, maxContextBytes = config.maxContextBytes ?? 12000;
  if (!Number.isInteger(deadlineMs) || deadlineMs < 100 || deadlineMs > 10000 || !Number.isInteger(maxContextBytes) || maxContextBytes < 1024 || maxContextBytes > 16384) fail('E_CONFIG', 'Invalid resource limits');
  const guarded = config.guardedTools ?? [];
  if (!Array.isArray(guarded) || guarded.length > 100 || guarded.some(n => typeof n !== 'string' || !/^[a-zA-Z0-9_.-]{1,160}$/.test(n) || n.includes('sage_'))) fail('E_CONFIG', 'Invalid guardedTools');
  if (Boolean(config.rsiPlanPath) !== Boolean(config.rsiStatePath) || (config.rsiPlanPath && new Set([config.planPath, config.statePath, config.rsiPlanPath, config.rsiStatePath]).size !== 4)) fail('E_CONFIG', 'RSI paths must be paired and distinct');
  const controller = await openContinuation({ root, planPath: config.planPath, statePath: config.statePath });
  const protectedFiles = [configPath, ...['agent-host.mjs', 'mcp.mjs', 'hook.mjs', 'continuation.mjs', 'rsi.mjs', 'rsi-process.mjs'].map(p => fileURLToPath(new URL(p, import.meta.url)))].filter(Boolean);
  const rsi = config.rsiPlanPath ? await openRSI({ root, planPath: config.rsiPlanPath, statePath: config.rsiStatePath,
    protectedPaths: async ({ signal }) => {
      const seen = await controller.observe({ signal });
      return [...new Set([config.planPath, config.statePath, config.planPath + '.lock', config.statePath + '.lock', 'AGENTS.md', 'CLAUDE.md', '.codex/config.toml', '.codex/hooks.json', '.claude/settings.json', '.claude/settings.local.json', '.mcp.json', ...seen.context.authority.map(a => a.path), ...protectedFiles.filter(p => inside(root, p)).map(p => relative(root, p).split(sep).join('/'))])];
    },
  }) : undefined;
  let owner, latest, session;
  const tools = definitions.filter(([name]) => rsi || !name.startsWith('sage_rsi_')).map(([name, description, inputSchema]) => ({ name, description, inputSchema }));
  async function refresh(signal, full = false) {
    const start = performance.now();
    const seen = full || !latest ? await controller.inspect({ signal }) : await controller.observe({ signal });
    let io = seen.io;
    if (seen.action) latest = seen;
    else if (seen.fingerprint !== latest.fingerprint || seen.revision !== latest.revision || ['revoked', 'expired', 'authority_changed'].includes(seen.status)) {
      latest = await controller.inspect({ signal });
      io = Object.fromEntries(Object.keys(seen.io).map(key => [key, seen.io[key] + latest.io[key]]));
    }
    if (latest.action !== 'reconcile' || latest.attempt?.id !== owner) owner = undefined;
    try { diagnostic?.({ operation: full ? 'inspect' : 'refresh', elapsedMs: performance.now() - start, io }); } catch { /* advisory only */ }
    return { ...latest, io };
  }
  function render(value) {
    const text = 'SAGE-Kit: current project documents own authority. Read the references and preserve scope. '
      + 'Use sage_begin before effects; a replay or reconcile requires checking actual effects before recording a result. '
      + 'Required evidence/review must be real. Completion awaits human acceptance. No implicit publication, new scope or RSI adoption. '
      + 'Hook reminders/denials cover configured events only; missing hooks do not imply permission.\n'
      + JSON.stringify({ action: owner && value.action === 'reconcile' ? 'working' : value.action, ...value.context, attempt: value.attempt });
    if (Buffer.byteLength(text) > maxContextBytes) fail('E_CONTEXT_BUDGET', 'Governance context exceeds limit; read authority explicitly');
    return text;
  }
  async function hook(event, signal) {
    if (!object(event) || typeof event.session_id !== 'string' || !event.session_id || typeof event.cwd !== 'string' || !isAbsolute(event.cwd)) fail('E_EVENT', 'Missing host event identity/cwd');
    if (!inside(root, await realpath(event.cwd))) { owner = undefined; fail('E_PROJECT', 'Host event is outside configured project'); }
    if (session && session !== event.session_id) { owner = undefined; fail('E_SESSION', 'One MCP connection must serve one execution owner'); }
    session = event.session_id;
    const kind = event.hook_event_name;
    if (!['SessionStart', 'UserPromptSubmit', 'PreToolUse', 'Stop', 'PreCompact', 'PostCompact', 'Interrupt'].includes(kind)) fail('E_EVENT', 'Unsupported governance event');
    if (kind === 'Interrupt' || (kind === 'SessionStart' && event.source !== 'compact')) owner = undefined;
    if (kind === 'PreToolUse' && (typeof event.tool_name !== 'string' || !event.tool_name || event.tool_name.length > 160)) fail('E_EVENT', 'PreToolUse requires tool_name');
    // Unselected tools have no filesystem checks. Selected tools perform bounded
    // input refresh, not historical evidence scans on every call.
    if (kind === 'PreToolUse' && !guarded.includes(event.tool_name)) return {};
    const value = await refresh(signal, kind !== 'PreToolUse');
    if (kind === 'PreToolUse') {
      if (!owner) return { hookSpecificOutput: { hookEventName: kind, permissionDecision: 'deny', permissionDecisionReason: `SAGE-Kit: ${value.action}; inspect governance and establish a fresh admitted attempt before effects.` } };
      // No allow decision: preserve all native permissions and other denials.
      return {};
    }
    const text = render(value);
    if (kind === 'Stop') {
      const stopActive = event.stop_hook_active === true || event.stop_hook_active === 'true';
      if (!stopActive && ['continue', 'reconcile'].includes(value.action)) return { decision: 'block', reason: text };
      return { systemMessage: text }; // no repeated automatic Stop loop
    }
    if (kind === 'PreCompact' || kind === 'PostCompact' || kind === 'Interrupt') return { systemMessage: text };
    return { hookSpecificOutput: { hookEventName: kind, additionalContext: text } };
  }
  async function call(name, args = {}, { signal: parent } = {}) {
    const signal = AbortSignal.any([...(parent ? [parent] : []), AbortSignal.timeout(typeof name === 'string' && name.startsWith('sage_rsi_') ? 180000 : deadlineMs)]);
    try {
      const tool = tools.find(t => t.name === name);
      if (!tool || !object(args) || Object.keys(args).some(k => !Object.hasOwn(tool.inputSchema.properties, k)) || tool.inputSchema.required.some(k => !Object.hasOwn(args, k))) fail('E_ARGUMENT', 'Unknown tool or invalid arguments');
      signal.throwIfAborted();
      if (name === 'sage_hook') return await hook(args.event, signal);
      if (name === 'sage_inspect') { const value = await refresh(signal, true); return { ...value, reminder: render(value) }; }
      if (name === 'sage_begin') {
        owner = undefined;
        const value = await controller.begin(args.stepId, args.attemptId, { signal });
        latest = undefined;
        if (!value.replayed) owner = value.attempt.id;
        return value;
      }
      if (name === 'sage_finish') { owner = undefined; latest = undefined; return await controller.finish(args.attemptId, args.result, { signal }); }
      const method = name.slice('sage_rsi_'.length);
      if (method === 'propose') return await rsi.propose(args, { signal });
      if (method === 'adopt' || method === 'rollback') return await rsi[method]({ signal, authorize: async challenge => {
        if (!authorize) fail('E_APPROVAL_UNAVAILABLE', 'Host human elicitation is unavailable');
        return await authorize(challenge, signal) === true;
      } });
      return await rsi[method]({ signal });
    } catch (error) {
      owner = undefined; latest = undefined;
      if (name === 'sage_hook') {
        const message = `SAGE-Kit governance unavailable: ${error.code ?? error.name}. Read authority explicitly; no permission is granted.`;
        if (!args?.event?.hook_event_name || args.event.hook_event_name === 'PreToolUse') return { continue: false, systemMessage: message, hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: message } };
        return { continue: false, stopReason: message, systemMessage: message };
      }
      throw error;
    }
  }
  return { tools, call };
}
