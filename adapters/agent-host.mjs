// Shared local host boundary. Transport/lifecycle failures never grant authority.
import { open, realpath, lstat } from 'node:fs/promises';
import { isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openContinuation } from './continuation.mjs';
import { openRSI } from './rsi.mjs';
import { openForgeEvidence } from './forge.mjs';

const fail = (code, message) => { throw Object.assign(new Error(message), { code }); };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const inside = (root, path) => { const p = relative(root, path); return p === '' || (!isAbsolute(p) && p !== '..' && !p.startsWith('..' + sep)); };
const schema = (properties = {}, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false });
const string = { type: 'string' };
const resultSchema = schema({
  outcome: { type: 'string', enum: ['passed', 'failed', 'not_executed'] },
  checks: { type: 'array', maxItems: 100, items: schema({ id: string, passed: { type: 'boolean' },
    evidence: { type: 'string', description: 'Project-relative path to the existing actual check log. Preserve failed evidence.' } }) },
  review: { type: 'string', description: 'Project-relative independent review evidence path, when the step requires review.' },
}, ['outcome', 'checks']);
// Standard host entrypoints are protected even before a file exists. Custom
// project-local host configuration must be mapped as authority as well.
export const hostProtectedPaths = Object.freeze(['AGENTS.md', 'CLAUDE.md', '.codex', '.claude', '.dsh', '.mcp.json', 'cordis.yml', 'cordis.yaml', 'cordis.patch.yml']);
const definitions = [
  ['sage_inspect', 'Read current governance, next admitted work and reconciliation needs.', schema()],
  ['sage_begin', 'Record a new admitted attempt before effects. Replayed attempts MUST NOT repeat effects.', schema({ stepId: string, attemptId: string })],
  ['sage_finish', 'Record actual outcome and checks [{id, passed, evidence}] using existing project-relative evidence files. Use only outcome, checks and optional review; never fabricate checks or human acceptance.', schema({ attemptId: string, result: resultSchema })],
  ['sage_hook', 'Host lifecycle governance reminder/check. Does not grant permissions or run work.', schema({ event: { type: 'object' } })],
  ['sage_forge_capture', 'Explicitly fetch configured Git platform evidence into an immutable local receipt. Remote content is untrusted; this does not grant acceptance or execution permission.', schema({ source: string, kind: { type: 'string', enum: ['issue', 'run'] }, id: { type: 'integer' }, expectedSha: string, workflowPath: string, requiredJobs: { type: 'array', items: string } }, ['source', 'kind', 'id'])],
  ['sage_rsi_propose', 'Propose a candidate from actual feedback in configured targets.', schema({ hypothesis: string, feedback: { type: 'array' }, files: { type: 'array' } })],
  ...['inspect', 'evaluate', 'recover', 'adopt', 'rollback', 'observe'].map(name => [`sage_rsi_${name}`, `Controlled RSI ${name}. Adopt/rollback require a separate human response through the host.`, schema()]),
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
    try { return JSON.parse(bytes.subarray(0, total).toString('utf8')); }
    catch { fail('E_CONFIG', 'Configuration JSON is invalid'); }
  } finally { await file.close(); }
}

// Called only at setup and explicit capture/RSI operations, never by hooks.
// Evidence cannot become a writable alias for governance or evaluation assets.
export async function checkForgeBoundary(config, root, authority, loadedPaths = [], signal) {
  if (!config.forge) return;
  signal?.throwIfAborted();
  const directory = resolve(root, config.forge.directory);
  const paths = [config.planPath, config.statePath, config.planPath + '.lock', config.statePath + '.lock',
    ...hostProtectedPaths,
    ...authority.map(ref => ref.path), ...loadedPaths];
  if (config.rsiPlanPath) {
    const parts = typeof config.rsiPlanPath === 'string' ? config.rsiPlanPath.split('/') : [];
    if (!parts.length || parts.length > 32 || isAbsolute(config.rsiPlanPath) || /[\\:\0]/.test(config.rsiPlanPath)
      || parts.some(part => !part || ['.', '..', '.git'].includes(part.toLowerCase()))) fail('E_CONFIG', 'Unsafe RSI plan path');
    const planPath = resolve(root, config.rsiPlanPath);
    if (!inside(root, planPath)) fail('E_CONFIG', 'RSI plan is outside the project');
    let current = root;
    for (const part of parts) {
      signal?.throwIfAborted();
      current = resolve(current, part);
      const info = await lstat(current);
      if (info.isSymbolicLink()) fail('E_CONFIG', 'RSI plan path must not contain symbolic links');
      if (current === planPath ? !info.isFile() : !info.isDirectory()) fail('E_CONFIG', 'RSI plan requires directory parents and a regular file');
    }
    const plan = await readConfig(planPath);
    for (const key of ['authority', 'inputs', 'targets']) {
      if (!Array.isArray(plan[key]) || plan[key].length > 128 || plan[key].some(path => typeof path !== 'string')) fail('E_CONFIG', 'Invalid RSI plan path set');
      paths.push(...plan[key]);
    }
    paths.push(config.rsiPlanPath, config.rsiStatePath, config.rsiPlanPath + '.lock', config.rsiStatePath + '.lock');
  }
  for (const name of paths) {
    const protectedPath = resolve(root, name);
    if (inside(directory, protectedPath) || inside(protectedPath, directory)) fail('E_CONFIG', 'Forge evidence directory overlaps governance, configuration or evaluation assets');
  }
  signal?.throwIfAborted();
}

export async function openAgentHost(config, { configPath, authorize, diagnostic } = {}) {
  if (!object(config) || !['codex', 'claude'].includes(config.host) || !isAbsolute(config.projectRoot ?? '')) fail('E_CONFIG', 'Explicit host and absolute projectRoot required');
  const root = await realpath(config.projectRoot);
  const deadlineMs = config.deadlineMs ?? 2000, maxContextBytes = config.maxContextBytes ?? 12000;
  if (!Number.isInteger(deadlineMs) || deadlineMs < 100 || deadlineMs > 10000 || !Number.isInteger(maxContextBytes) || maxContextBytes < 1024 || maxContextBytes > 16384) fail('E_CONFIG', 'Invalid resource limits');
  const guarded = config.guardedTools ?? [];
  if (!Array.isArray(guarded) || guarded.length > 100 || guarded.some(n => typeof n !== 'string' || !/^[a-zA-Z0-9_.-]{1,160}$/.test(n) || n.includes('sage_'))) fail('E_CONFIG', 'Invalid guardedTools');
  if (Boolean(config.rsiPlanPath) !== Boolean(config.rsiStatePath) || (config.rsiPlanPath && new Set([config.planPath, config.statePath, config.rsiPlanPath, config.rsiStatePath]).size !== 4)) fail('E_CONFIG', 'RSI paths must be paired and distinct');
  const automatic = config.rsiAutomaticPolicy != null;
  if (automatic && !config.rsiPlanPath) fail('E_CONFIG', 'Automatic RSI requires explicit RSI paths');
  const controller = await openContinuation({ root, planPath: config.planPath, statePath: config.statePath });
  const protectedFiles = [configPath, ...['agent-host.mjs', 'mcp.mjs', 'hook.mjs', 'continuation.mjs', 'rsi.mjs', 'rsi-process.mjs', 'forge.mjs', 'package.json'].map(p => fileURLToPath(new URL(p, import.meta.url)))].filter(Boolean);
  const forge = config.forge ? await openForgeEvidence({ root, directory: config.forge.directory, sources: config.forge.sources }) : undefined;
  if (forge) await checkForgeBoundary(config, root, (await controller.observe()).context.authority, protectedFiles);
  const rsi = config.rsiPlanPath ? await openRSI({ root, planPath: config.rsiPlanPath, statePath: config.rsiStatePath,
    ...(automatic ? { automaticPolicy: config.rsiAutomaticPolicy } : {}),
    protectedPaths: async ({ signal }) => {
      const seen = await controller.observe({ signal });
      if (automatic && ['revoked', 'expired', 'authority_changed'].includes(seen.status)) fail('E_RSI_AUTHORITY', 'Current project continuation authority is not valid for automatic RSI');
      await checkForgeBoundary(config, root, seen.context.authority, protectedFiles, signal);
      const paths = [...new Set([config.planPath, config.statePath, config.planPath + '.lock', config.statePath + '.lock', ...hostProtectedPaths, ...(forge ? [config.forge.directory] : []), ...seen.context.authority.map(a => a.path), ...protectedFiles.filter(p => inside(root, p)).map(p => relative(root, p).split(sep).join('/'))])];
      return { paths, binding: seen.fingerprint };
    },
  }) : undefined;
  let owner, latest, session;
  const automaticDescriptions = {
    sage_rsi_evaluate: 'Run the fixed comparison; a proven improvement may be adopted within the preauthorized project branch, then checked and rolled back on failure. No per-candidate human approval.',
    sage_rsi_rollback: 'Restore this settled adopted round under its preauthorized policy; preserve third-party changes. This is not a human approval.',
    sage_rsi_observe: 'Explicitly rerun the fixed postcheck for the preauthorized adopted round and roll back on regression. No background loop.',
  };
  const tools = definitions.filter(([name]) => (rsi || !name.startsWith('sage_rsi_')) && (forge || name !== 'sage_forge_capture')
    && (automatic ? name !== 'sage_rsi_adopt' : name !== 'sage_rsi_observe'))
    .map(([name, description, inputSchema]) => ({ name, description: automatic && name.startsWith('sage_rsi_')
      ? automaticDescriptions[name] ?? `Controlled RSI ${name.slice('sage_rsi_'.length)} within the explicitly preauthorized project branch; final acceptance remains human.` : description, inputSchema }));
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
      + (rsi ? automatic ? 'RSI is preauthorized only for the configured development branch and policy. Evaluate may adopt and postcheck; observe or rollback use that policy, never a fabricated human response. Final acceptance remains human.\n' : 'RSI adoption and rollback require a separate human approval; evaluate alone does not adopt.\n' : '')
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
    const signal = AbortSignal.any([...(parent ? [parent] : []), AbortSignal.timeout(name === 'sage_forge_capture' ? 30000 : typeof name === 'string' && name.startsWith('sage_rsi_') ? 180000 : deadlineMs)]);
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
      if (name === 'sage_forge_capture') {
        await checkForgeBoundary(config, root, (await controller.observe({ signal })).context.authority, protectedFiles, signal);
        return await forge.capture(args, { signal });
      }
      const method = name.slice('sage_rsi_'.length);
      if (method === 'propose') return await rsi.propose(args, { signal });
      if (!automatic && (method === 'adopt' || method === 'rollback')) return await rsi[method]({ signal, authorize: async challenge => {
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
