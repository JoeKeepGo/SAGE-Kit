// Real Codex CLI, isolated home, and loopback-only deterministic Responses API.
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { access, mkdir, mkdtemp, writeFile, readFile, readdir, rm, cp } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

export const codexBinary = process.env.SAGE_CODEX_BIN;
export const codexAvailable = Boolean(codexBinary);
export const codexSkipReason = 'Set SAGE_CODEX_BIN to the vetted native Codex executable; no installation or real provider is used.';
const toml = value => JSON.stringify(value);

export async function createCodexHost(t, { projectRoot, config, withMcp = true, hooks = true, compactProbe = false, codeMode = false, observeHooks = false, guardedTools = ['exec_command', 'apply_patch'] } = {}) {
  if (!codexBinary) throw new Error(codexSkipReason);
  await access(codexBinary);
  const stage = await mkdtemp(join(tmpdir(), 'sage-codex-host-'));
  const home = join(stage, 'home'), codexHome = join(home, '.codex');
  await mkdir(codexHome, { recursive: true });
  const adapterRoot = process.env.SAGE_AGENT_ADAPTER_DIR ?? join(stage, 'adapter');
  if (!process.env.SAGE_AGENT_ADAPTER_DIR) await cp(new URL('../../adapters/', import.meta.url), adapterRoot, { recursive: true });
  const configPath = join(stage, 'sage-config.json');
  await writeFile(configPath, JSON.stringify(config ?? { projectRoot, planPath: 'plan.json', statePath: 'state.json', host: 'codex', guardedTools, deadlineMs: 2000, maxContextBytes: 12000 }));
  const requests = [], unexpected = [], children = new Set();
  const terminate = child => { try { if (process.platform === 'win32') child.kill('SIGKILL'); else process.kill(-child.pid, 'SIGKILL'); } catch {} };
  let actions = [], responseNumber = 0;
  const server = createServer(async (req, res) => {
    try {
      let raw = '';
      for await (const chunk of req) { raw += chunk; if (raw.length > 4 * 1024 * 1024) throw new Error('Fixture request budget exceeded'); }
      if (req.method !== 'POST' || !req.url.endsWith('/responses')) {
        unexpected.push({ method: req.method, path: req.url }); res.writeHead(404).end('Fixture route not supported'); return;
      }
      if (requests.length >= 64) throw new Error('Fixture request count exceeded');
      const request = JSON.parse(raw); requests.push(request);
      const compacting = compactProbe && JSON.stringify(request.input).includes('You are performing a CONTEXT CHECKPOINT COMPACTION');
      const selected = compacting ? { text: 'Compact summary: native fixture pending first step. Do not invent evidence.' } : actions.shift();
      const action = typeof selected === 'function' ? await selected(request) : selected;
      const n = ++responseNumber;
      const item = action?.input !== undefined ? { id: `ct_${n}`, type: 'custom_tool_call', call_id: `call_${n}`, name: action.tool.split('.').at(-1), ...(action.tool.includes('.') ? { namespace: action.tool.slice(0, action.tool.lastIndexOf('.')) } : {}), input: action.input, status: 'completed' } : action?.tool ? { id: `fc_${n}`, type: 'function_call', call_id: `call_${n}`, name: action.tool.split('.').at(-1), ...(action.tool.includes('.') ? { namespace: action.tool.slice(0, action.tool.lastIndexOf('.')) } : {}), arguments: JSON.stringify(action.args ?? {}), status: 'completed' }
        : { id: `msg_${n}`, type: 'message', role: 'assistant', status: 'completed', content: [{ type: 'output_text', text: action?.text ?? 'Fixture complete.', annotations: [] }] };
      const response = { id: `resp_${n}`, object: 'response', created_at: Math.floor(Date.now() / 1000), model: request.model, status: 'completed', output: [item], usage: { input_tokens: action?.forceCompact ? 200000 : 10, output_tokens: 10, total_tokens: action?.forceCompact ? 200010 : 20 } };
      res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
      for (const event of [
        { type: 'response.created', response: { ...response, status: 'in_progress', output: [] } },
        { type: 'response.output_item.added', output_index: 0, item: { ...item, status: 'in_progress', ...(action?.input !== undefined ? { input: '' } : action?.tool ? { arguments: '' } : { content: [] }) } },
        { type: 'response.output_item.done', output_index: 0, item },
        { type: 'response.completed', response },
      ]) res.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
      res.end();
    } catch (error) { unexpected.push({ error: error.message }); res.writeHead(500).end('Fixture failed'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${server.address().port}/v1`;
  // Fixed test model metadata enables the real patch tool and keeps MCP discovery
  // stable. The loopback provider returns scripted responses, never a paid model.
  const catalogPath = join(stage, 'fixture-model.json');
  await writeFile(catalogPath, JSON.stringify({ models: [{
    slug: 'sage-fixture', display_name: 'Local deterministic fixture', description: 'Native host acceptance fixture',
    default_reasoning_level: 'low', supported_reasoning_levels: [{ effort: 'low', description: 'Fixture' }],
    shell_type: 'shell_command', visibility: 'list', supported_in_api: true, priority: 0,
    base_instructions: 'Run the requested local fixture.', supports_reasoning_summaries: false,
    support_verbosity: false, default_verbosity: null, apply_patch_tool_type: 'freeform',
    truncation_policy: { mode: 'tokens', limit: 10000 }, supports_parallel_tool_calls: true,
    context_window: 272000, auto_compact_token_limit: null, experimental_supported_tools: [],
    supports_search_tool: false, tool_mode: codeMode ? 'code_mode_only' : null,
  }] }));
  const settings = [
    'model = "sage-fixture"', `model_catalog_json = ${toml(catalogPath)}`, 'model_provider = "fixture"', 'approval_policy = "never"', 'sandbox_mode = "danger-full-access"',
    'web_search = "disabled"', 'model_reasoning_effort = "low"', ...(compactProbe ? ['model_auto_compact_token_limit = 100000'] : []),
    '[model_providers.fixture]', 'name = "Local deterministic fixture"', `base_url = ${toml(endpoint)}`, 'wire_api = "responses"', 'requires_openai_auth = false', 'supports_websockets = false', 'request_max_retries = 0', 'stream_max_retries = 0',
    '[features]', 'hooks = true', 'apps = false', ...(codeMode ? ['code_mode = true', 'code_mode_only = true'] : []),
  ];
  if (withMcp) settings.push('[mcp_servers.sage]', `command = ${toml(process.execPath)}`, `args = ${JSON.stringify([join(adapterRoot, 'mcp.mjs'), configPath])}`, 'startup_timeout_sec = 10', 'tool_timeout_sec = 5');
  await writeFile(join(codexHome, 'config.toml'), settings.join('\n') + '\n');
  const hookTrace = join(stage, 'hook-inputs.jsonl');
  if (hooks && withMcp) {
    const hook = event => ({ hooks: [{ type: 'mcp_tool', server: 'sage', tool: 'sage_hook', timeout: 5, input: { event: { hook_event_name: '${hook_event_name}', cwd: '${cwd}', session_id: '${session_id}', ...(event === 'PreToolUse' ? { tool_name: '${tool_name}' } : {}), ...(event === 'Stop' ? { stop_hook_active: '${stop_hook_active}' } : {}), ...(event === 'SessionStart' ? { source: '${source}' } : {}) } } }] });
    const selectedHooks = Object.fromEntries(['UserPromptSubmit', 'PreToolUse', 'Stop'].map(name => [name, [hook(name)]]));
    const quote = value => "'" + value.replaceAll("'", "'\"'\"'") + "'";
    selectedHooks.SessionStart = [{ matcher: '^(startup|resume|clear|fork)$', hooks: [{ type: 'command', command: [process.execPath, join(adapterRoot, 'hook.mjs'), configPath].map(quote).join(' '), timeout: 5 }] }];
    selectedHooks.SessionStart.push({ ...hook('SessionStart'), matcher: '^compact$' });
    if (observeHooks) {
      const observer = join(stage, 'observe-hook.mjs');
      await writeFile(observer, `import { appendFile } from 'node:fs/promises';
let input = ''; for await (const chunk of process.stdin) input += chunk;
await appendFile(process.argv[2], JSON.stringify(JSON.parse(input)) + '\\n');
process.stdout.write('{}\\n');
`);
      selectedHooks.PreToolUse.unshift({ hooks: [{ type: 'command', command: [process.execPath, observer, hookTrace].map(quote).join(' '), timeout: 5 }] });
    }
    await writeFile(join(codexHome, 'hooks.json'), JSON.stringify({ hooks: selectedHooks }));
  }
  const env = { PATH: process.env.PATH, HOME: home, USERPROFILE: home, CODEX_HOME: codexHome, TMPDIR: stage, LANG: 'C.UTF-8' };
  const run = async (script = [], { resume, prompt = 'Continue the approved local fixture.' } = {}) => {
    actions = [...script];
    const start = requests.length;
    const args = ['exec', '--skip-git-repo-check', '--dangerously-bypass-hook-trust', '--ignore-rules', '--json', '-C', projectRoot];
    if (resume) args.push('resume', resume);
    args.push(prompt);
    const child = spawn(codexBinary, args, { env, cwd: projectRoot, stdio: ['ignore', 'pipe', 'pipe'], detached: process.platform !== 'win32' }); children.add(child);
    let stdout = '', stderr = '', timeout;
    let overflow = false;
    const append = (text, bytes) => { if (text.length + bytes.length > 4 * 1024 * 1024) { overflow = true; terminate(child); return text; } return text + bytes; };
    child.stdout.on('data', b => { stdout = append(stdout, b); }); child.stderr.on('data', b => { stderr = append(stderr, b); });
    const exit = await new Promise((resolve, reject) => {
      timeout = setTimeout(() => { terminate(child); reject(new Error(`Codex fixture timeout: ${stderr.slice(-2500)}`)); }, 20000);
      child.once('error', reject); child.once('close', (code, signal) => resolve({ code, signal }));
    }).finally(() => { clearTimeout(timeout); terminate(child); children.delete(child); });
    if (overflow) throw new Error('Codex fixture output budget exceeded');
    const events = stdout.split('\n').filter(Boolean).map(line => { try { return JSON.parse(line); } catch { return { raw: line }; } });
    return { ...exit, events, stdout, stderr, requests: requests.slice(start), unusedActions: actions.length, unexpected: [...unexpected] };
  };
  t.after(async () => { for (const child of children) terminate(child); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await rm(stage, { recursive: true, force: true }); });
  // Linux-only measurement follows this fixture's descendants; never scans /proc.
  const sampleMcp = async () => {
    if (process.platform !== 'linux') throw new Error('Native process counters require Linux /proc');
    const queue = [...children].map(child => child.pid), seen = new Set(), matches = [];
    while (queue.length) {
      const pid = queue.shift();
      if (seen.has(pid)) continue;
      seen.add(pid);
      if (seen.size > 128) throw new Error('Fixture descendant budget exceeded');
      try {
        const command = (await readFile(`/proc/${pid}/cmdline`, 'utf8')).split('\0');
        if (command.includes(join(adapterRoot, 'mcp.mjs')) && command.includes(configPath)) matches.push(pid);
        // A multithreaded host may spawn the child from any worker thread.
        // Threads can disappear after open: procfs then reports ESRCH, not ENOENT.
        // Only discovery skips these races; the chosen MCP counters must read successfully.
        const tids = await readdir(`/proc/${pid}/task`);
        if (tids.length > 256) throw new Error('Fixture thread budget exceeded');
        for (const tid of tids) {
          try { queue.push(...(await readFile(`/proc/${pid}/task/${tid}/children`, 'utf8')).trim().split(/\s+/).filter(Boolean).map(Number)); }
          catch (error) { if (!['ENOENT', 'ESRCH'].includes(error.code)) throw error; }
        }
      } catch (error) { if (!['ENOENT', 'ESRCH'].includes(error.code)) throw error; }
    }
    if (matches.length !== 1) throw new Error(`Expected one fixture MCP process, found ${matches.length}`);
    const pid = matches[0];
    const stat = await readFile(`/proc/${pid}/stat`, 'utf8');
    const fields = stat.slice(stat.lastIndexOf(')') + 2).trim().split(/\s+/);
    const io = Object.fromEntries((await readFile(`/proc/${pid}/io`, 'utf8')).trim().split('\n').map(line => { const [key, value] = line.split(':'); return [key, Number(value.trim())]; }));
    return { pid, startTicks: Number(fields[19]), userTicks: Number(fields[11]), systemTicks: Number(fields[12]), io };
  };
  const observedHooks = async () => (await readFile(hookTrace, 'utf8').catch(error => { if (error.code === 'ENOENT') return ''; throw error; })).split('\n').filter(Boolean).map(JSON.parse);
  return { run, stage, codexHome, adapterRoot, requests, sampleMcp, observedHooks };
}

export const nativeCall = (name, args = {}) => request => {
  const available = request.tools ?? request.input.filter(item => item.type === 'additional_tools').flatMap(item => item.tools);
  const flat = available.flatMap(tool => tool.type === 'namespace' ? tool.tools.map(item => ({ ...item, name: tool.name + '.' + item.name })) : [tool]);
  const tool = flat.find(tool => tool.name === name || tool.name?.endsWith('.' + name) || tool.name?.endsWith('__' + name));
  if (!tool) throw new Error('Native tool missing: ' + name + '; available: ' + flat.map(t => t.name).join(', '));
  return tool.type === 'custom' ? { tool: tool.name, input: typeof args === 'string' ? args : JSON.stringify(args) } : { tool: tool.name, args };
};
