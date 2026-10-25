// Actual native Claude Code host, driven by a loopback deterministic Messages
// fixture. No model provider, default home, credential, or network API is used.
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';

export function claudeEnv(home, endpoint = 'http://127.0.0.1:1') {
  return {
    PATH: `${dirname(process.execPath)}:/usr/bin:/bin`, HOME: home,
    TMPDIR: home, XDG_CONFIG_HOME: join(home, 'xdg'), CLAUDE_CONFIG_DIR: join(home, 'config'),
    ANTHROPIC_BASE_URL: endpoint, ANTHROPIC_API_KEY: 'local-fixture-not-a-secret',
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: '1', DISABLE_AUTOUPDATER: '1',
    DISABLE_TELEMETRY: '1', DISABLE_ERROR_REPORTING: '1',
    HTTP_PROXY: 'http://127.0.0.1:1', HTTPS_PROXY: 'http://127.0.0.1:1',
    ALL_PROXY: 'http://127.0.0.1:1', NO_PROXY: '127.0.0.1,localhost',
    ENABLE_TOOL_SEARCH: 'false', CLAUDE_CODE_MAX_OUTPUT_TOKENS: '1024',
    MCP_TIMEOUT: '4000', MCP_TOOL_TIMEOUT: '4000',
  };
}

function stream(res, model, blocks, id) {
  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
  const send = (type, value) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...value })}\n\n`);
  send('message_start', { message: { id: `msg_fixture_${id}`, type: 'message', role: 'assistant', model,
    content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 10, output_tokens: 0 } } });
  blocks.forEach((block, index) => {
    if (block.type === 'tool_use') {
      send('content_block_start', { index, content_block: { ...block, input: {} } });
      send('content_block_delta', { index, delta: { type: 'input_json_delta', partial_json: JSON.stringify(block.input) } });
    } else {
      send('content_block_start', { index, content_block: { type: 'text', text: '' } });
      send('content_block_delta', { index, delta: { type: 'text_delta', text: block.text } });
    }
    send('content_block_stop', { index });
  });
  send('message_delta', { delta: { stop_reason: blocks.some(x => x.type === 'tool_use') ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 10 } });
  send('message_stop', {});
  res.end();
}

export async function runClaude({ binary, cwd, home, settings = {}, mcpServers = {}, responses = [], extraArgs = [], timeoutMs = 25000 }) {
  await mkdir(home, { recursive: true });
  const settingsPath = join(home, 'settings.json'), mcpPath = join(home, 'mcp.json');
  await writeFile(settingsPath, JSON.stringify(settings));
  await writeFile(mcpPath, JSON.stringify({ mcpServers }));
  const requests = [], traffic = [];
  let responseIndex = 0, requestError;
  const server = createServer(async (req, res) => {
    try {
      let text = '';
      for await (const part of req) { text += part; if (text.length > 2 * 1024 * 1024) throw Error('fixture request budget exceeded'); }
      traffic.push(req.url);
      const body = text ? JSON.parse(text) : {};
      if (req.url.startsWith('/v1/messages/count_tokens')) { res.setHeader('content-type', 'application/json'); res.end('{"input_tokens":10}'); return; }
      if (!req.url.startsWith('/v1/messages')) { res.writeHead(404); res.end('{}'); return; }
      requests.push(body);
      const response = responses[responseIndex++];
      const blocks = typeof response === 'function' ? await response(body, requests) : response;
      stream(res, body.model, blocks ?? [{ type: 'text', text: 'fixture complete' }], responseIndex);
    } catch (error) { requestError = error; res.writeHead(500); res.end('{}'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const args = ['--restricted', '--setting-sources', '', '--strict-mcp-config', '--mcp-config', mcpPath,
    '--settings', settingsPath, '--model', 'claude-sonnet-4-6', '--permission-mode', 'dontAsk',
    '--permission-prompts', 'none', '--tools', 'Write,Read,Bash', '--disable-slash-commands',
    '--no-chrome', '--no-session-persistence', '--output-format', 'stream-json', '--verbose',
    '--include-hook-events', '--max-turns', '12', ...extraArgs, '-p', 'Run the local deterministic governance fixture.'];
  const child = spawn(binary, args, { cwd, env: claudeEnv(home, `http://127.0.0.1:${server.address().port}`), detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '', stderr = '', timedOut = false;
  const kill = () => { if (child.pid) { try { process.kill(-child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; } } };
  child.stdout.on('data', data => { stdout += data; if (stdout.length > 2 * 1024 * 1024) kill(); });
  child.stderr.on('data', data => { stderr += data; if (stderr.length > 1024 * 1024) kill(); });
  const timer = setTimeout(() => { timedOut = true; kill(); }, timeoutMs);
  try {
    const end = await new Promise((resolve, reject) => { child.once('error', reject); child.once('close', (code, signal) => resolve({ code, signal })); });
    if (requestError) throw requestError;
    return { ...end, timedOut, stdout, stderr, requests, traffic, args,
      events: stdout.split('\n').filter(line => line.startsWith('{')).map(line => JSON.parse(line)) };
  } finally { clearTimeout(timer); kill(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
}
