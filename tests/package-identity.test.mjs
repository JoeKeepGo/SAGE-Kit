import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, writeFile, rm, cp } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const execute = promisify(execFile);
const source = fileURLToPath(new URL('../adapters/', import.meta.url));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

async function initialize(entry, configPath, cwd, env) {
  const child = spawn(process.execPath, [entry, configPath], { cwd, env, stdio: ['pipe', 'pipe', 'pipe'] });
  const closed = new Promise(resolve => child.once('close', (code, signal) => resolve({ code, signal })));
  let timer;
  try {
    const reply = await new Promise((resolve, reject) => {
      let output = '', errors = '';
      timer = setTimeout(() => reject(new Error('Installed MCP initialize exceeded 10 seconds')), 10000);
      child.once('error', reject);
      child.stdin.on('error', reject);
      child.stderr.on('data', bytes => {
        errors += bytes.toString();
        if (errors.length > 16384) reject(new Error('Installed MCP stderr budget exceeded'));
      });
      child.stdout.on('data', bytes => {
        output += bytes.toString();
        if (output.length > 65536) { reject(new Error('Installed MCP output budget exceeded')); return; }
        const end = output.indexOf('\n');
        if (end < 0) return;
        try {
          const message = JSON.parse(output.slice(0, end));
          assert.equal(message.jsonrpc, '2.0'); assert.equal(message.id, 1);
          assert.equal(message.error, undefined);
          assert.ok(message.result?.serverInfo);
          resolve(message.result.serverInfo);
        } catch (error) { reject(error); }
      });
      child.once('close', () => reject(new Error(`Installed MCP closed before initialize: ${errors}`)));
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: {
        protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'package-identity-test', version: '1' },
      } }) + '\n');
    });
    child.stdin.end();
    // The same deadline also covers clean EOF shutdown.
    await Promise.race([closed, new Promise((_, reject) => {
      clearTimeout(timer);
      timer = setTimeout(() => reject(new Error('Installed MCP EOF shutdown exceeded 10 seconds')), 10000);
    })]).then(result => assert.deepEqual(result, { code: 0, signal: null }));
    return reply;
  } finally {
    clearTimeout(timer);
    if (child.exitCode === null) child.kill('SIGKILL');
    await closed;
  }
}

async function verifyCandidate(installed, expected) {
  const metadata = JSON.parse(await readFile(join(installed, 'package.json'), 'utf8'));
  assert.deepEqual(metadata, expected, 'installed metadata must match the candidate source');
  const files = {};
  for (const name of ['package.json', ...expected.files]) {
    const bytes = await readFile(join(installed, name));
    assert.deepEqual(bytes, await readFile(join(source, name)), `${name}: installed payload differs from candidate source`);
    files[name] = digest(bytes);
  }
  return files;
}

test('offline artifact initializes from its installed location and rejects stale delivery', { timeout: 90000, skip: process.platform === 'win32' && 'This npm subprocess check runs in the POSIX CI job' }, async t => {
  const root = await mkdtemp(join(tmpdir(), 'sage-package-identity-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const home = join(root, 'home'); await mkdir(home);
  const userConfig = join(root, 'user.npmrc'), globalConfig = join(root, 'global.npmrc');
  await writeFile(userConfig, ''); await writeFile(globalConfig, '');
  const env = { PATH: `${dirname(process.execPath)}:${process.env.PATH ?? '/usr/bin:/bin'}`, HOME: home, TMPDIR: root,
    npm_config_userconfig: userConfig, npm_config_globalconfig: globalConfig, npm_config_cache: join(root, 'cache') };
  const npm = args => execute('npm', args, { cwd: root, env, timeout: 30000, maxBuffer: 1024 * 1024 });
  const metadata = JSON.parse(await readFile(join(source, 'package.json'), 'utf8'));
  const pack = async (directory, label) => {
    const destination = join(root, label); await mkdir(destination);
    const { stdout } = await npm(['pack', directory, '--offline', '--ignore-scripts', '--pack-destination', destination, '--json']);
    const [artifact] = JSON.parse(stdout);
    return join(destination, artifact.filename);
  };
  const install = async (artifact, label) => {
    const destination = join(root, label);
    await npm(['install', '--prefix', destination, '--offline', '--ignore-scripts', '--legacy-peer-deps', '--no-audit', '--no-fund', '--package-lock=false', artifact]);
    return join(destination, 'node_modules', ...metadata.name.split('/'));
  };
  const configPath = join(root, 'config.json');
  await writeFile(configPath, JSON.stringify({ host: 'codex', projectRoot: root, planPath: 'plan.json', statePath: 'state.json', guardedTools: [] }));
  await writeFile(join(root, 'SPEC.md'), 'Temporary package identity check only; no product work.\n');
  await writeFile(join(root, 'plan.json'), JSON.stringify({ version: 1, goal: 'Check installed MCP identity', authority: ['SPEC.md'],
    constraints: ['No external operations'], maxAttempts: 1, expiresAt: new Date(Date.now() + 60000).toISOString(), revoked: false,
    steps: [{ id: 'gate', objective: 'Await human acceptance', dependsOn: [], scope: ['evidence'], checks: [], requiresReview: false, admitted: true, humanGate: true }] }));

  const artifact = process.env.SAGE_DSH_TARBALL ? resolve(process.env.SAGE_DSH_TARBALL) : await pack(source, 'pack');
  const artifactHash = digest(await readFile(artifact));
  const installed = await install(artifact, 'installed');
  const files = await verifyCandidate(installed, metadata);
  const serverInfo = await initialize(join(installed, 'mcp.mjs'), configPath, root, env);
  assert.deepEqual(serverInfo, { name: 'sage-kit-local', version: metadata.version });
  assert.equal(digest(await readFile(artifact)), artifactHash);
  t.diagnostic(JSON.stringify({ artifact: { filename: artifact.split('/').at(-1), sha256: artifactHash },
    package: { name: metadata.name, version: metadata.version }, serverInfo, files, offline: true, lifecycleScripts: false }));

  await t.test('an internally consistent older artifact cannot pass as this candidate', async () => {
    const staleSource = join(root, 'stale-source'); await cp(source, staleSource, { recursive: true });
    const staleMetadata = { ...metadata, version: '0.0.0-stale-delivery-fixture' };
    await writeFile(join(staleSource, 'package.json'), JSON.stringify(staleMetadata));
    const staleArtifact = await pack(staleSource, 'stale-pack');
    const staleInstalled = await install(staleArtifact, 'stale-installed');
    const staleInfo = await initialize(join(staleInstalled, 'mcp.mjs'), configPath, root, env);
    assert.equal(staleInfo.version, staleMetadata.version, 'self-consistent identity alone is insufficient');
    await assert.rejects(verifyCandidate(staleInstalled, metadata), /installed metadata must match/);
    t.diagnostic(JSON.stringify({ counterexample: 'stale artifact rejected against candidate source', sha256: digest(await readFile(staleArtifact)), serverInfo: staleInfo }));
  });
});
