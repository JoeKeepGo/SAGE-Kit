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

test('DSH CLI installs the exact bundle and runs governed development plus separately approved RSI adoption and rollback', { skip, timeout: 60000 }, async t => {
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
  await writeFile(join(project, 'policy.txt'), 'old policy\n');
  await writeFile(join(project, 'rsi-check.mjs'), "import{readFileSync}from'node:fs';const ok=readFileSync('policy.txt','utf8')==='new policy\\n';console.log(ok?'policy check passed':'policy check failed');process.exit(ok?0:1);\n");
  let failure;
  try { await execute(process.execPath, ['rsi-check.mjs'], { cwd: project, env, timeout: 3000, maxBuffer: 4096 }); }
  catch (error) { failure = error; }
  assert.equal(failure?.code, 1, 'the original policy must produce actual failure evidence');
  await writeFile(join(project, 'rsi-feedback.txt'), `Observed original policy check exit 1:\n${failure.stdout}${failure.stderr}`);
  await writeFile(join(project, 'rsi-plan.json'), JSON.stringify({ version: 1, authority: ['authority.md'], inputs: ['policy.txt', 'rsi-check.mjs'], targets: ['policy.txt'], command: [process.execPath, 'rsi-check.mjs'], expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, maxEvaluations: 2, timeoutMs: 2000, maxOutputBytes: 4096 }));
  const services = ['dsh-agent', 'dsh-session', 'dsh-session-projection', 'dsh-llm', 'dsh-system-prompt', 'dsh-tools', 'dsh-agent-loop', 'dsh-user-approval'].map(name => ({ id: name, name: '@deepseek-ai/' + name, ...(name === 'dsh-system-prompt' ? { config: { includeHarnessIdentity: false, includeRuntimeContext: false } } : {}) }));
  // JSON is valid YAML. The actual profile include/loader consumes this layer;
  // the application does not instantiate a second Context or load the adapter.
  await writeFile(join(profile, 'cordis.patch.yml'), JSON.stringify([
    { id: 'sage-kit-dsh', disabled: false, config: { projectRoot: project, planPath: 'plan.json', statePath: 'state.json', rsiPlanPath: 'rsi-plan.json', rsiStatePath: 'rsi-state.json', guardedTools: ['fixture_write'] } },
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
  assert.equal(evidence.requests.length, 9);
  assert.equal(evidence.writes, 1);
  assert.match(JSON.stringify(evidence.requests[0].messages), /Governed profile fixture/);
  for (const name of ['sage_begin', 'sage_finish', 'sage_inspect']) assert.ok(evidence.requests[0].tools.some(tool => tool.name === name));
  const results = evidence.events.filter(event => event.type === 'tool/result');
  assert.equal(results.length, 7);
  assert.ok(results.every(event => event.data.message.isError !== true));
  assert.equal(evidence.events.findLast(event => event.type === 'turn/end')?.data.reason.kind, 'completed');
  assert.equal(await readFile(join(project, 'output.txt'), 'utf8'), 'delivered');
  assert.equal(JSON.parse(await readFile(join(project, 'state.json'), 'utf8')).attempts[0].outcome, 'passed');
  assert.equal(evidence.adoptedPolicyObserved, true);
  assert.equal(await readFile(join(project, 'policy.txt'), 'utf8'), 'old policy\n');
  assert.equal(JSON.parse(await readFile(join(project, 'rsi-state.json'), 'utf8')).status, 'rolled_back');
  assert.deepEqual(evidence.approvals.map(item => item.toolName), ['sage_rsi_adopt', 'sage_rsi_rollback']);
  const approvals = evidence.events.filter(event => event.type === 'approval/asked');
  const decisions = evidence.events.filter(event => event.type === 'approval/decided');
  assert.equal(approvals.length, 2);
  assert.deepEqual(decisions.map(event => event.data.outcome), ['allowed-once', 'allowed-once']);
  assert.equal(new Set(approvals.map(event => event.data.callId)).size, 2);
  for (const approval of approvals) assert.ok(decisions.some(decision => decision.data.id === approval.data.id));
  for (const name of ['sage_rsi_propose', 'sage_rsi_inspect', 'sage_rsi_evaluate', 'sage_rsi_adopt', 'sage_rsi_rollback', 'sage_rsi_recover']) assert.ok(evidence.requests[0].tools.some(tool => tool.name === name));
  assert.equal(createHash('sha256').update(await readFile(tarball)).digest('hex'), tarballHash, 'artifact must not change during its acceptance run');
  t.diagnostic(JSON.stringify({ evidence: 'real DSH CLI/profile loader + deterministic fixture application', tarball, sha256: tarballHash, dshVersion: cliManifest.version, schemaComplete: true, requests: evidence.requests.length, writes: evidence.writes, approvalDecisions: decisions.map(event => event.data.outcome), policyRestored: true, boundary: 'Not stock headless application or real-model quality validation.' }));
});
