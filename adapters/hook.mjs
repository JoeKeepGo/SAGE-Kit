// One-shot startup/compaction reminder for hosts whose MCP is not ready yet.
// Never install this command on per-tool hooks; use the connected MCP transport.
import { openAgentHost, readConfig } from './agent-host.mjs';

try {
  const chunks = []; let size = 0;
  const timer = setTimeout(() => { process.stderr.write('SAGE-Kit hook input timeout\n'); process.exit(2); }, 2000);
  timer.unref();
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 65536) throw new Error('Hook input exceeds 64 KiB');
    chunks.push(chunk);
  }
  clearTimeout(timer);
  const event = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (event.hook_event_name !== 'SessionStart') throw new Error('Command helper only supports SessionStart');
  const configPath = process.argv[2];
  const host = await openAgentHost(await readConfig(configPath), { configPath });
  process.stdout.write(JSON.stringify(await host.call('sage_hook', { event })) + '\n');
} catch (error) {
  process.stdout.write(JSON.stringify({ continue: false, stopReason: 'SAGE-Kit startup reminder unavailable; explicitly inspect current authority.', systemMessage: `SAGE-Kit: ${error.code ?? error.name}` }) + '\n');
  process.exitCode = 2;
}
