// Actual DSH CLI/profile-loader acceptance. The local application supplies a
// deterministic model double; no default profile or provider adapter is loaded.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, writeFile, readFile, cp, rm } from 'node:fs/promises';
import { join, resolve, dirname, delimiter } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';

const execute = promisify(execFile);
const configured = Boolean(process.env.SAGE_DSH_NODE_MODULES && process.env.SAGE_DSH_TARBALL);
const skip = configured ? false : 'Set both SAGE_DSH_NODE_MODULES and SAGE_DSH_TARBALL to test the actual installed DSH profile and explicit local package; no artifact is built or downloaded implicitly.';

test('DSH CLI discovers the exact local bundle, enables it, projects schema and runs a checked task', { skip, timeout: 60000 }, async t => {
  const tarball = resolve(process.env.SAGE_DSH_TARBALL);
  const modules = resolve(process.env.SAGE_DSH_NODE_MODULES);
  const cli = join(modules, '@deepseek-ai/dsh/lib/bin.js');
  const cliManifest = JSON.parse(await readFile(join(modules, '@deepseek-ai/dsh/package.json'), 'utf8'));
  assert.equal(cliManifest.version, '0.2.1-rc.2');
  const tarballHash = createHash('sha256').update(await readFile(tarball)).digest('hex');
  const root = await mkdtemp(join(tmpdir(), 'sage-dsh-profile-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const home = join(root, 'dsh-home'), profile = join(home, 'profiles/sage-probe'), project = join(root, 'project');
  await mkdir(profile, { recursive: true });
  await mkdir(project);
  await mkdir(join(root, 'cache'));
  await writeFile(join(root, 'npm-user.rc'), '');
  await writeFile(join(root, 'npm-global.rc'), '');
  // Deliberately omit credentials, proxy settings, NODE_OPTIONS and inherited
  // profile configuration. npm reads only the isolated configs/cache below.
  const env = {
    PATH: [dirname(process.execPath), '/usr/bin', '/bin', process.env.PATH ?? ''].join(delimiter),
    DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1',
    npm_config_cache: join(root, 'cache'),
    npm_config_userconfig: join(root, 'npm-user.rc'),
    npm_config_globalconfig: join(root, 'npm-global.rc'),
  };
  await writeFile(join(profile, 'package.json'), JSON.stringify({ name: 'sage-isolated-profile-test', private: true, dsh: { profile: { bundles: ['@sage-kit/dsh-plugin'] } } }, null, 2));
  async function command(label, bin, args, cwd = profile) {
    try {
      return await execute(bin, args, { env, cwd, timeout: 15000, killSignal: 'SIGKILL', maxBuffer: 4 * 1024 * 1024 });
    } catch (error) {
      t.diagnostic(`${label} failed (${error.code ?? error.signal}): ${error.stderr ?? error.message}\n${error.stdout ?? ''}`);
      throw error;
    }
  }
  const installArgs = ['install', '--legacy-peer-deps', '--offline', '--ignore-scripts', '--no-audit', '--no-fund', '--package-lock=false', tarball];
  if (process.env.SAGE_NPM_CLI) await command('offline npm install', process.execPath, [resolve(process.env.SAGE_NPM_CLI), ...installArgs]);
  else await command('offline npm install', process.platform === 'win32' ? 'npm.cmd' : 'npm', installArgs);
  const installed = JSON.parse(await readFile(join(profile, 'node_modules/@sage-kit/dsh-plugin/package.json'), 'utf8'));
  assert.equal(installed.name, '@sage-kit/dsh-plugin');
  assert.ok(installed.dsh?.bundle?.patch, 'the installed product must declare its own bundle patch');
  await cp(new URL('./fixtures/dsh-profile-app.mjs', import.meta.url), join(profile, 'fixture-runner.mjs'));
  await writeFile(join(project, 'authority.md'), 'Keep governance and check actual outputs.');
  await writeFile(join(project, 'plan.json'), JSON.stringify({ version: 1, goal: 'Governed profile fixture', authority: ['authority.md'], constraints: ['No network', 'No publication'], maxAttempts: 2, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps: [{ id: 'first', objective: 'Write and check one isolated output', dependsOn: [], scope: ['output.txt', 'check.txt'], checks: ['test'], requiresReview: false, admitted: true, humanGate: false }] }));
  const services = ['dsh-agent', 'dsh-session', 'dsh-session-projection', 'dsh-llm', 'dsh-system-prompt', 'dsh-tools', 'dsh-agent-loop'].map(name => ({ id: name, name: '@deepseek-ai/' + name, ...(name === 'dsh-system-prompt' ? { config: { includeHarnessIdentity: false, includeRuntimeContext: false } } : {}) }));
  // JSON is valid YAML. The actual profile include/loader consumes this layer;
  // the application does not instantiate a second Context or load the adapter.
  await writeFile(join(profile, 'cordis.patch.yml'), JSON.stringify([
    { id: 'sage-kit-dsh', disabled: false, config: { projectRoot: project, planPath: 'plan.json', statePath: 'state.json', guardedTools: ['fixture_write'] } },
    { insert: [...services, { id: 'fixture-runner', name: join(profile, 'fixture-runner.mjs'), config: { projectRoot: project, evidencePath: join(root, 'runtime-evidence.json') } }] },
  ], null, 2));
  const version = await command('version', process.execPath, [cli, '--version'], project);
  assert.equal(version.stdout.trim(), '0.2.1-rc.2');
  const dump = await command('dump-config', process.execPath, [cli, '--profile', 'sage-probe', '--dump-config'], project);
  assert.equal(dump.stderr, '');
  assert.match(dump.stdout, /@sage-kit\/dsh-plugin/);
  assert.match(dump.stdout, /disabled: false/);
  const schemaOutput = await command('dump-config-schema', process.execPath, [cli, '--profile', 'sage-probe', '--dump-config-schema'], project);
  assert.equal(schemaOutput.stderr, '');
  assert.equal(JSON.parse(schemaOutput.stdout)['x-cordis'].complete, true);
  const run = await command('profile boot', process.execPath, [cli, '--profile', 'sage-probe'], project);
  assert.equal(run.stderr, '');
  const evidence = JSON.parse(await readFile(join(root, 'runtime-evidence.json'), 'utf8'));
  assert.equal(evidence.ok, true, evidence.failure);
  assert.deepEqual(evidence.errors, []);
  assert.equal(evidence.requests.length, 4);
  assert.equal(evidence.writes, 1);
  assert.match(JSON.stringify(evidence.requests[0].messages), /Governed profile fixture/);
  for (const name of ['sage_begin', 'sage_finish', 'sage_inspect']) assert.ok(evidence.requests[0].tools.some(tool => tool.name === name));
  const results = evidence.events.filter(event => event.type === 'tool/result');
  assert.equal(results.length, 3);
  assert.ok(results.every(event => event.data.message.isError !== true));
  assert.equal(evidence.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
  assert.equal(await readFile(join(project, 'output.txt'), 'utf8'), 'delivered');
  assert.equal(JSON.parse(await readFile(join(project, 'state.json'), 'utf8')).attempts[0].outcome, 'passed');
  assert.equal(createHash('sha256').update(await readFile(tarball)).digest('hex'), tarballHash, 'artifact must not change during its acceptance run');
  t.diagnostic(JSON.stringify({ evidence: 'real DSH CLI/profile loader + deterministic fixture application', tarball, sha256: tarballHash, dshVersion: cliManifest.version, schemaComplete: true, requests: evidence.requests.length, writes: evidence.writes, boundary: 'Not stock headless application or real-model quality validation.' }));
});
