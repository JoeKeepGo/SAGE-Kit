// Bounded JSON-RPC stdio transport, owned by one host connection. No polling.
import { pathToFileURL } from 'node:url';
import { openAgentHost, readConfig } from './agent-host.mjs';

export async function serve(configPath, input = process.stdin, output = process.stdout) {
  const config = await readConfig(configPath);
  const lifetime = new AbortController();
  const requests = new Map(), answers = new Map();
  let initialized = false, capabilities = {}, protocol, pending = Buffer.alloc(0), queue = Promise.resolve(), sequence = 0, closed = false;
  function close() {
    if (closed) return;
    closed = true; lifetime.abort();
    for (const request of requests.values()) request.abort();
    input.destroy();
  }
  // Stdout is protocol-only. Backpressure is bounded; a non-reading host loses
  // this connection instead of accumulating logs or waiting indefinitely.
  function send(message) {
    if (closed) return;
    const bytes = JSON.stringify({ jsonrpc: '2.0', ...message }) + '\n';
    if (Buffer.byteLength(bytes) > 2 * 1024 * 1024 || output.writableLength > 2 * 1024 * 1024) { close(); return; }
    output.write(bytes);
  }
  const host = await openAgentHost(config, { configPath, authorize: async (challenge, signal) => {
    if (!capabilities.elicitation || (Object.keys(capabilities.elicitation).length > 0 && !capabilities.elicitation.form)) throw Object.assign(new Error('Host form elicitation unavailable'), { code: 'E_APPROVAL_UNAVAILABLE' });
    const id = `sage-approval-${++sequence}`;
    const result = await new Promise((resolve, reject) => {
      const abort = () => { answers.delete(id); reject(signal.reason ?? new Error('Cancelled')); };
      signal.throwIfAborted();
      signal.addEventListener('abort', abort, { once: true });
      answers.set(id, message => { signal.removeEventListener('abort', abort); answers.delete(id); resolve(message.result); });
      send({ id, method: 'elicitation/create', params: {
        ...(protocol === '2025-06-18' ? {} : { mode: 'form' }),
        message: 'SAGE-Kit requests a one-time HUMAN decision for this exact RSI change. Review the complete bound challenge; do not auto-answer.\n' + JSON.stringify(challenge),
        requestedSchema: { type: 'object', properties: { approve: { type: 'boolean', title: 'Approve this exact change once' } }, required: ['approve'] },
      } });
    });
    return result?.action === 'accept' && result.content?.approve === true;
  } });
  async function handle(message, controller) {
    const id = message.id;
    try {
      controller.signal.throwIfAborted();
      let result;
      if (message.method === 'initialize' && !initialized) {
        protocol = ['2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25'].includes(message.params?.protocolVersion) ? message.params.protocolVersion : '2025-06-18';
        capabilities = message.params?.capabilities ?? {}; initialized = true;
        result = { protocolVersion: protocol, capabilities: { tools: {} }, serverInfo: { name: 'sage-kit-local', version: '0.0.0-rebuild-r4' }, instructions: 'Project authority governs all work. Read sage_inspect before effects; replayed attempts require reconciliation. This connection belongs to one execution owner.' };
      } else if (!initialized) throw new Error('Initialize exactly once before requests');
      else if (message.method === 'ping') result = {};
      else if (message.method === 'tools/list') result = { tools: host.tools };
      else if (message.method === 'tools/call') {
        try {
          const value = await host.call(message.params?.name, message.params?.arguments ?? {}, { signal: AbortSignal.any([lifetime.signal, controller.signal]) });
          result = { content: [{ type: 'text', text: JSON.stringify(value) }], structuredContent: value };
        } catch (error) {
          result = { isError: true, content: [{ type: 'text', text: JSON.stringify({ code: error.code ?? error.name, message: error.message }) }] };
        }
      } else { send({ id, error: { code: -32601, message: 'Unsupported method' } }); return; }
      send({ id, result });
    } catch (error) { send({ id, error: { code: -32600, message: error.message } }); }
    finally { requests.delete(id); }
  }
  function accept(line) {
    let message;
    try { message = JSON.parse(line); } catch { send({ id: null, error: { code: -32700, message: 'Invalid JSON' } }); return; }
    if (!message || message.jsonrpc !== '2.0' || Array.isArray(message)) { send({ id: null, error: { code: -32600, message: 'Invalid request' } }); return; }
    if (!Object.hasOwn(message, 'method') && answers.has(message.id)) {
      // A JSON-RPC response has exactly one result/error. Protocol failures
      // must never become human approval, even if they also contain "accept".
      const valid = Object.hasOwn(message, 'result') && !Object.hasOwn(message, 'error');
      answers.get(message.id)(valid ? message : {}); return;
    }
    if (message.method === 'notifications/cancelled') { requests.get(message.params?.requestId)?.abort(); return; }
    if (!Object.hasOwn(message, 'id')) return;
    if (!['string', 'number'].includes(typeof message.id) || requests.has(message.id)) { close(); return; }
    if (requests.size >= 16) { send({ id: message.id, error: { code: -32000, message: 'Request queue limit reached' } }); return; }
    const controller = new AbortController(); requests.set(message.id, controller);
    queue = queue.then(() => handle(message, controller));
  }
  const stop = () => close();
  process.once('SIGTERM', stop); process.once('SIGINT', stop);
  output.on('error', stop);
  try {
    await new Promise(resolve => {
      input.on('data', chunk => {
        if (closed) return;
        // Cap a single line even if a peer never emits its newline.
        pending = Buffer.concat([pending, chunk]);
        let index;
        while (!closed && (index = pending.indexOf(10)) >= 0) {
          if (index > 1024 * 1024) { close(); resolve(); return; }
          const line = pending.subarray(0, index).toString('utf8'); pending = pending.subarray(index + 1);
          if (line.trim()) accept(line);
        }
        if (pending.length > 1024 * 1024 || closed) { close(); resolve(); }
      });
      input.once('end', () => { close(); resolve(); });
      input.once('error', () => { close(); resolve(); });
      lifetime.signal.addEventListener('abort', resolve, { once: true });
    });
    await queue;
  } finally {
    close(); process.removeListener('SIGTERM', stop); process.removeListener('SIGINT', stop);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  serve(process.argv[2]).catch(error => { process.stderr.write(`SAGE-Kit MCP startup failed: ${error.code ?? error.name}\n`); process.exitCode = 1; });
}
