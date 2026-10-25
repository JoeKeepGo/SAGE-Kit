import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, writeFile, rm, lstat, cp, access } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { openContinuation } from '../adapters/continuation.mjs';
import { openAgentHost } from '../adapters/agent-host.mjs';

const execute = promisify(execFile);

const capture = JSON.parse(await readFile(new URL('../examples/rebuild/taluvia-mapping.json', import.meta.url), 'utf8'));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const parse = bytes => JSON.parse(bytes.toString('utf8'));

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'sage-project-mapping-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = async (path, content) => {
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), content);
  };
  return { root, put };
}

function plan(authority, steps) {
  return {
    version: 1, goal: 'Verify explicit project mapping without promoting source status',
    authority, constraints: ['Source documents retain their authority and IDs', 'No network, product execution, or automatic acceptance'],
    maxAttempts: 4, expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, steps,
  };
}

function step(id, objective, checks, extra = {}) {
  return { id, objective, dependsOn: [], scope: ['receipts'], checks, requiresReview: false, admitted: true, humanGate: false, ...extra };
}

test('minimal adoption example executes its actual check and stops at human acceptance', async t => {
  const f = await fixture(t);
  await cp(new URL('../examples/rebuild/minimal/', import.meta.url), f.root, { recursive: true });
  const expiresAt = new Date(Date.now() + 60000).toISOString();
  await execute(process.execPath, ['prepare.mjs', expiresAt], { cwd: f.root, timeout: 5000 });
  const configPath = join(f.root, 'host.json');
  const config = parse(await readFile(configPath));
  const host = await openAgentHost(config, { configPath });
  const before = await host.call('sage_inspect');
  assert.equal(before.action, 'continue'); assert.equal(before.step.id, 'greeting');
  assert.equal(before.context.expiresAt, expiresAt);
  for (const id of ['MIN-REQ-01', 'MIN-ACC-01']) assert.ok(before.step.objective.includes(id));
  const event = { hook_event_name: 'PreToolUse', cwd: f.root, session_id: 'minimal-example', tool_name: 'apply_patch' };
  assert.equal((await host.call('sage_hook', { event })).hookSpecificOutput.permissionDecision, 'deny');
  const begun = await host.call('sage_begin', { stepId: 'greeting', attemptId: 'greeting-1' });
  assert.equal(begun.replayed, false);
  assert.deepEqual(await host.call('sage_hook', { event }), {});
  await f.put('output/greeting.txt', 'Hello, SAGE-Kit!\n');
  const { stdout, stderr } = await execute(process.execPath, ['check.mjs'], { cwd: f.root, timeout: 5000, maxBuffer: 16384 });
  assert.match(stdout, /MIN-ACC-01 PASS/);
  const evidence = 'evidence/greeting-1.log';
  await mkdir(join(f.root, 'evidence'));
  await writeFile(join(f.root, evidence), `command: node check.mjs\nexit: 0\n${stdout}${stderr}`, { flag: 'wx' });
  await host.call('sage_finish', { attemptId: 'greeting-1', result: {
    outcome: 'passed', checks: [{ id: 'greeting', passed: true, evidence }],
  } });
  const after = await host.call('sage_inspect');
  assert.equal(after.action, 'human_gate'); assert.equal(after.step.id, 'human_acceptance');
  await assert.rejects(host.call('sage_begin', { stepId: 'human_acceptance', attemptId: 'must-not-accept' }), /human_gate/);
  assert.equal((await host.call('sage_inspect')).action, 'human_gate');
  for (const name of ['SPEC.md', 'check.mjs', 'prepare.mjs', 'plan.template.json', 'host.template.json']) {
    assert.deepEqual(await readFile(join(f.root, name)), await readFile(new URL(`../examples/rebuild/minimal/${name}`, import.meta.url)));
  }
  t.diagnostic(JSON.stringify({ command: 'node check.mjs', exitCode: 0, stdout, finalAction: after.action,
    step: after.step.id, evidenceSha256: sha256(await readFile(join(f.root, evidence))), boundary: 'temporary example via shared host API; not native host or human acceptance' }));
});

test('minimal example setup rejects missing, expired and unbounded expiry before writing a round', async t => {
  const f = await fixture(t);
  await cp(new URL('../examples/rebuild/minimal/', import.meta.url), f.root, { recursive: true });
  for (const args of [[], [new Date(Date.now() - 60000).toISOString()], [new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString()]]) {
    await assert.rejects(execute(process.execPath, ['prepare.mjs', ...args], { cwd: f.root, timeout: 5000 }), /Supply an explicit ISO expiry in the next hour/);
    for (const name of ['plan.json', 'host.json']) await assert.rejects(access(join(f.root, name)), { code: 'ENOENT' });
  }
});

test('minimal example local documentation links resolve', async t => {
  const documents = [new URL('../adapters/README.md', import.meta.url),
    new URL('../examples/rebuild/minimal/README.md', import.meta.url), new URL('../examples/rebuild/minimal/SPEC.md', import.meta.url),
    new URL('../examples/rebuild/from-docset/README.md', import.meta.url), new URL('../docs/rebuild/from-docset.md', import.meta.url)];
  let checked = 0;
  for (const document of documents) {
    const markdown = await readFile(document, 'utf8');
    for (const [, target] of markdown.matchAll(/\[[^\]]*\]\(([^\s)]+)\)/g)) {
      if (/^[a-z]+:/i.test(target) || target.startsWith('#')) continue;
      await access(new URL(target.split('#')[0], document)); checked++;
    }
  }
  assert.ok(checked >= 6);
  t.diagnostic(`${checked} local links resolved across ${documents.length} affected documents`);
});

test('from-docset example starts without implementation and cannot satisfy fixed acceptance or skip dependencies', async t => {
  const f = await fixture(t);
  for (const name of ['SPEC.md', 'check.mjs', 'plan.template.json', 'host.template.json']) {
    await cp(new URL(`../examples/rebuild/from-docset/${name}`, import.meta.url), join(f.root, name));
  }
  for (const name of ['src', 'bin', 'tests', 'package.json', 'README.md']) {
    await assert.rejects(access(join(f.root, name)), { code: 'ENOENT' });
  }
  await execute(process.execPath, [new URL('../examples/rebuild/minimal/prepare.mjs', import.meta.url).pathname,
    new Date(Date.now() + 60000).toISOString()], { cwd: f.root, timeout: 5000 });
  const configPath = join(f.root, 'host.json');
  const host = await openAgentHost(parse(await readFile(configPath)), { configPath });
  const initial = await host.call('sage_inspect');
  assert.equal(initial.step.id, 'engine');
  assert.match(initial.step.objective, /TL-01\/TL-02/);
  await assert.rejects(host.call('sage_begin', { stepId: 'cli', attemptId: 'skip-engine' }));
  await host.call('sage_begin', { stepId: 'engine', attemptId: 'engine-1' });
  await assert.rejects(execute(process.execPath, ['check.mjs', 'core'], { cwd: f.root, timeout: 5000 }), /ERR_MODULE_NOT_FOUND/);
  await assert.rejects(host.call('sage_finish', { attemptId: 'engine-1', result: { outcome: 'passed', checks: [] } }));
  assert.equal((await host.call('sage_inspect')).action, 'reconcile');
  t.diagnostic('Empty implementation is not completion; positive development evidence belongs to the real-model trial');
});

async function recordMappingCheck(f, controller, id, check) {
  assert.equal((await controller.inspect()).step.id, id);
  await controller.begin(id, `mapping-${id}`);
  // Missing mapped acceptance evidence must not silently complete a task.
  await assert.rejects(controller.finish(`mapping-${id}`, { outcome: 'passed', checks: [] }));
  await f.put('receipts/mapping.json', JSON.stringify({ check, result: 'references verified', productExecution: 'NOT_EXECUTED' }));
  await controller.finish(`mapping-${id}`, {
    outcome: 'passed', checks: [{ id: check, passed: true, evidence: 'receipts/mapping.json' }],
  });
}

test('a flat small-project charter maps original requirement/acceptance IDs and gates without rewriting its source', async t => {
  const f = await fixture(t);
  const sources = {
    'brief.txt': 'Owner: CSV utility project\nREQ-CSV-01: Export UTF-8 CSV with a header.\nACCEPT-CSV-01: Header precedes rows.\nStatus: PLANNED_NOT_STARTED\n',
    'todo.json': JSON.stringify({ task: 'CSV-EXPORT', requirement: 'brief.txt#REQ-CSV-01', acceptance: 'brief.txt#ACCEPT-CSV-01', status: 'PLANNED_NOT_STARTED', implementation: 'export.py' }),
  };
  for (const [path, value] of Object.entries(sources)) await f.put(path, value);
  const config = { root: f.root, planPath: 'work-order.json', statePath: '.observed/round.json' };
  const mapping = plan(Object.keys(sources), [
    step('verify-mapping', 'Check todo.json CSV-EXPORT -> brief.txt REQ-CSV-01 / ACCEPT-CSV-01', ['reference-integrity']),
    step('CSV-EXPORT', 'Implement brief.txt REQ-CSV-01; acceptance ACCEPT-CSV-01', ['ACCEPT-CSV-01'], { dependsOn: ['verify-mapping'], humanGate: true, scope: ['export.py'] }),
  ]);
  await f.put(config.planPath, JSON.stringify(mapping));
  const controller = await openContinuation(config);
  const context = JSON.stringify((await controller.inspect()).context);
  for (const ref of ['brief.txt', 'todo.json', 'REQ-CSV-01', 'ACCEPT-CSV-01']) assert.ok(context.includes(ref));
  await recordMappingCheck(f, controller, 'verify-mapping', 'reference-integrity');
  assert.equal((await controller.inspect()).action, 'human_gate');
  await assert.rejects(controller.begin('CSV-EXPORT', 'unauthorized-product-work'));
  for (const [path, value] of Object.entries(sources)) assert.equal(await readFile(join(f.root, path), 'utf8'), value);
  assert.equal(parse(await readFile(join(f.root, 'todo.json'))).status, 'PLANNED_NOT_STARTED');
  const before = await controller.inspect();
  await f.put('scratch/irrelevant.txt', 'Unrelated notes do not change the mapped authority.');
  assert.equal((await controller.inspect()).fingerprint, before.fingerprint);
  await f.put('brief.txt', sources['brief.txt'].replace('with a header', 'without a header'));
  assert.equal((await controller.inspect()).action, 'authority_changed');
  await assert.rejects(controller.begin('CSV-EXPORT', 'stale-mapping'));
});

test('Taluvia 1.12 bounded source capture maps P0 IDs read-only and refuses product admission', {
  skip: !process.env.SAGE_TALUVIA_DOCSET && 'Set SAGE_TALUVIA_DOCSET to the explicit local Taluvia_Space_Docset_v1.12.0 directory; live source mapping was not checked',
}, async t => {
  const sourceRoot = process.env.SAGE_TALUVIA_DOCSET;
  const bytesByPath = new Map();
  // Fixed 14-file, < 1 MiB capture, not a recursive docset scan. Reject a changed
  // source rather than silently refreshing the recorded mapping evidence.
  assert.equal(capture.sources.length, 14);
  assert.ok(capture.sources.reduce((sum, source) => sum + source.bytes, 0) < 1024 * 1024);
  for (const source of capture.sources) {
    const path = join(sourceRoot, source.path);
    const stat = await lstat(path);
    assert.ok(stat.isFile() && !stat.isSymbolicLink(), source.path);
    assert.equal(stat.size, source.bytes, `${source.path}: capture is stale`);
    const bytes = await readFile(path);
    assert.equal(sha256(bytes), source.sha256, `${source.path}: capture is stale; review source changes`);
    for (const selector of source.selectors) assert.ok(bytes.toString('utf8').includes(selector), `${source.path}: missing ${selector}`);
    bytesByPath.set(source.path, bytes);
  }
  // Always recheck the same bounded sources, including when a later assertion fails.
  t.after(async () => {
    for (const [path, bytes] of bytesByPath) assert.equal(sha256(await readFile(join(sourceRoot, path))), sha256(bytes), `${path}: source changed during mapping`);
  });
  const release = parse(bytesByPath.get('RELEASE.json'));
  assert.equal(release.docsetVersion, capture.sourceVersion);
  assert.equal(release.currentDecisions, 'governance/decisions-1.12.md');
  assert.equal(release.productIntegration, capture.productAcceptance);
  const m = capture.mapping;
  const tasks = parse(bytesByPath.get('data/tasks.json'));
  assert.ok(tasks.every(task => task.status === capture.executionStatus));
  const task = tasks.find(task => task.id === m.taskId);
  assert.ok(task);
  assert.equal(task.specId, m.specId);
  assert.equal(task.phase, m.phase);
  assert.equal(task.plannedPath, m.plannedPath);
  assert.deepEqual(task.interfacePrerequisites, m.interfacePrerequisites);
  assert.deepEqual(task.focusedAcceptanceTests, m.acceptanceIds);
  const acceptances = parse(bytesByPath.get('data/acceptance.json'));
  assert.ok(acceptances.every(acceptance => acceptance.status === capture.productAcceptance));
  for (const id of m.acceptanceIds) {
    const acceptance = acceptances.find(item => item.id === id);
    assert.equal(acceptance?.specId, m.specId);
    assert.equal(acceptance.normativeSource, 'specs/SPEC-00/SPEC.md');
    assert.deepEqual(acceptance.evidence, []);
  }
  const requirements = parse(bytesByPath.get('data/requirements-1.12.json'));
  for (const [index, id] of m.requirementIds.entries()) {
    const requirement = requirements.find(item => item.id === id);
    assert.equal(requirement?.specId, m.specId);
    assert.equal(requirement.status, m.requirementStatus);
    assert.equal(requirement.verificationStatus, m.requirementVerification);
    assert.equal(requirement.normativeClause, m.normativeClauses[index]);
  }
  const stages = parse(bytesByPath.get('data/stages.json'));
  assert.equal(stages.docsetVersion, capture.observedVersionDifference.docsetVersion);
  assert.equal(stages.revision, capture.observedVersionDifference.revision);
  assert.equal(stages.stages.find(stage => stage.id === m.phase).status, capture.executionStatus);

  // All controller state and writes stay in an independent temporary fixture.
  // The captured source files keep their original relative paths and raw bytes.
  const f = await fixture(t);
  for (const [path, bytes] of bytesByPath) await f.put(path, bytes);
  await f.put('mapping/capture.json', JSON.stringify(capture));
  const config = { root: f.root, planPath: '.sage/mapping-plan.json', statePath: '.sage/observed.json' };
  const mapped = plan([...bytesByPath.keys(), 'mapping/capture.json'], [
    step('verify-mapping', `${m.taskId} -> ${m.requirementIds.join(', ')} -> ${m.acceptanceIds.join(', ')}; ${m.probeId}; fixture reference check only`, ['reference-integrity']),
    step(m.taskId, `${task.title}; original source data/tasks.json; ${m.normativeClauses.join(', ')}`, m.acceptanceIds, { admitted: false, requiresReview: true, scope: m.plannedPath.split(' + ').map(path => path.replace(/\/$/, '')) }),
  ]);
  mapped.constraints.push(`Taluvia remains ${capture.executionStatus}; product acceptance ${capture.productAcceptance}; no product commands`);
  await f.put(config.planPath, JSON.stringify(mapped));
  const controller = await openContinuation(config);
  const inspected = await controller.inspect();
  for (const source of capture.sources) {
    assert.equal(inspected.context.authority.find(item => item.path === source.path)?.sha256, source.sha256);
  }
  for (const id of [m.taskId, ...m.requirementIds, ...m.acceptanceIds, m.probeId]) assert.ok(JSON.stringify(inspected.context).includes(id));
  await recordMappingCheck(f, controller, 'verify-mapping', 'reference-integrity');
  assert.equal((await controller.inspect()).action, 'blocked');
  await assert.rejects(controller.begin(m.taskId, 'must-not-start-product'));
  for (const [path, bytes] of bytesByPath) assert.equal(sha256(await readFile(join(f.root, path))), sha256(bytes));
  // Alter only the isolated copy to show prior mapping evidence cannot authorize
  // continuation after a normative source changes. The original stays untouched.
  await f.put('governance/decisions-1.12.md', Buffer.concat([bytesByPath.get('governance/decisions-1.12.md'), Buffer.from('\nFixture-only authority change.\n')]));
  assert.equal((await controller.inspect()).action, 'authority_changed');
  await assert.rejects(controller.begin(m.taskId, 'stale-source'));
});
