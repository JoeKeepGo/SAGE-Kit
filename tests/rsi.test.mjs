import test from 'node:test';
import assert from 'node:assert/strict';
import fileSystem, { mkdtemp, mkdir, readFile, writeFile, rm, stat, utimes, symlink } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { tmpdir, platform, release, arch } from 'node:os';
import { createHash } from 'node:crypto';
import { syncBuiltinESMExports } from 'node:module';
import { openRSI } from '../adapters/rsi.mjs';
import { runFixed } from '../adapters/rsi-process.mjs';

const options = { timeout: 15000, skip: process.platform === 'win32' ? 'Real evaluator requires supported POSIX process-tree cleanup' : false };
const evaluator = `import {readFileSync} from 'node:fs';
const actual=readFileSync('strategy.txt','utf8');
if(actual==='GOOD'){process.stdout.write('check passed');}
else{process.stderr.write('check failed: expected GOOD');process.exitCode=3;}`;
const sha = value => createHash('sha256').update(value).digest('hex');

async function fixture(t, overrides = {}) {
  const root = await mkdtemp(join(tmpdir(), 'sage-rsi-component-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const put = async (path, content) => {
    await mkdir(dirname(join(root, path)), { recursive: true });
    await writeFile(join(root, path), content);
  };
  await put('authority.md', 'Only the admitted strategy may change; checks and commands are protected.\n');
  await put('strategy.txt', 'BAD');
  await put('rules.txt', 'protected evaluator policy\n');
  await put('evaluate.mjs', overrides.evaluator ?? evaluator);
  const failure = await runFixed([process.execPath, '-e', "if(require('node:fs').readFileSync('strategy.txt','utf8')!=='GOOD'){process.stderr.write('Real strategy check failed');process.exitCode=3}"], {
    cwd: root, timeoutMs: 2000, maxOutputBytes: 4096,
  });
  assert.equal(failure.exitCode, 3);
  await put('feedback/failure.txt', JSON.stringify(failure));
  const plan = { version: 1, authority: ['authority.md'], inputs: ['strategy.txt', 'rules.txt', 'evaluate.mjs'],
    targets: ['strategy.txt'], command: [process.execPath, 'evaluate.mjs'],
    expiresAt: '2099-01-01T00:00:00.000Z', revoked: false, maxEvaluations: 2,
    timeoutMs: 2000, maxOutputBytes: 4096, ...overrides.plan };
  await put('rsi-plan.json', JSON.stringify(plan));
  const config = { root, planPath: 'rsi-plan.json', statePath: 'state/rsi.json' };
  const controller = await openRSI(config);
  const candidate = { hypothesis: 'Replacing the incorrect strategy repairs the observed fixed check',
    feedback: [{ path: 'feedback/failure.txt', kind: 'failure' }], files: [{ path: 'strategy.txt', content: 'GOOD' }] };
  const evaluate = async (input = candidate) => { await controller.propose(input); return controller.evaluate(); };
  return { root, put, plan, config, controller, candidate, evaluate };
}

test('real failure evidence becomes a fixed comparison, separately approved adoption, and approved rollback', options, async t => {
  const f = await fixture(t);
  const evaluated = await f.evaluate();
  assert.equal(evaluated.next, 'human_approval');
  assert.equal(evaluated.evaluation.eligible, true);
  assert.deepEqual(evaluated.evaluation.runs.map(r => [r.kind, r.exitCode, r.protection]), [['baseline', 3, true], ['candidate', 0, true]]);
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD');
  await assert.rejects(f.controller.adopt(), { code: 'E_RSI_APPROVAL' });
  await assert.rejects(f.controller.adopt({ authorize: async () => false }), { code: 'E_RSI_APPROVAL' });
  let adoption;
  const adopted = await f.controller.adopt({ authorize: async challenge => {
    adoption = structuredClone(challenge);
    assert.equal(challenge.action, 'adopt');
    assert.equal(challenge.proposalDigest, evaluated.proposal.digest);
    assert.equal(challenge.evaluationDigest, evaluated.evaluation.digest);
    assert.deepEqual(challenge.changes, [{ path: 'strategy.txt', before: 'BAD', after: 'GOOD' }]);
    return true; // Test controller approval applies only to this isolated fixture.
  } });
  assert.equal(adopted.status, 'adopted');
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'GOOD');
  await assert.rejects(f.controller.rollback(), { code: 'E_RSI_APPROVAL' });
  const rolled = await f.controller.rollback({ authorize: async challenge => {
    assert.equal(challenge.action, 'rollback');
    assert.notEqual(challenge.stateDigest, adoption.stateDigest);
    return true;
  } });
  assert.equal(rolled.status, 'rolled_back');
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD');
});

for (const side of ['baseline', 'candidate']) {
  test(`${side} protection violation cannot become an eligible comparison`, options, async t => {
    const condition = side === 'baseline' ? "actual==='BAD'" : "actual==='GOOD'";
    const code = evaluator.replace("if(actual==='GOOD')", `if(${condition}){(await import('node:fs')).writeFileSync('rules.txt','cheated');}\nif(actual==='GOOD')`);
    const f = await fixture(t, { evaluator: code });
    const evaluated = await f.evaluate();
    assert.equal(evaluated.evaluation.eligible, false);
    assert.equal(evaluated.evaluation.runs.find(run => run.kind === side).protection, false);
    if (side === 'baseline') assert.equal(evaluated.evaluation.runs.length, 1);
    await assert.rejects(f.controller.adopt({ authorize: async () => true }), { code: 'E_RSI_NOT_ELIGIBLE' });
    assert.equal(await readFile(join(f.root, 'rules.txt'), 'utf8'), 'protected evaluator policy\n');
  });
}

test('builder parameters cannot replace evaluator commands, targets, or verdicts', options, async t => {
  const f = await fixture(t);
  for (const extra of [{ command: [process.execPath, '-e', 'process.exit(0)'] }, { targets: ['evaluate.mjs'] }, { passed: true }]) {
    await assert.rejects(f.controller.propose({ ...f.candidate, ...extra }), { code: 'E_RSI_INVALID' });
  }
  await assert.rejects(f.controller.propose({ ...f.candidate, files: [{ path: 'evaluate.mjs', content: 'process.exit(0)' }] }), { code: 'E_RSI_PROTECTED' });
  assert.equal((await f.controller.inspect()).status, 'empty');
});

for (const changed of ['feedback', 'authority', 'plan', 'protected input', 'target']) {
  test(`${changed} change invalidates adoption after a passing evaluation`, options, async t => {
    const f = await fixture(t);
    await f.evaluate();
    const changes = {
      feedback: ['feedback/failure.txt', 'different failure record'], authority: ['authority.md', 'new project authority'],
      plan: ['rsi-plan.json', JSON.stringify({ ...f.plan, maxEvaluations: 3 })],
      'protected input': ['rules.txt', 'changed evaluator policy'], target: ['strategy.txt', 'OTHER'],
    };
    await f.put(...changes[changed]);
    let requested = false;
    await assert.rejects(f.controller.adopt({ authorize: async () => { requested = true; return true; } }), { code: 'E_RSI_STALE' });
    assert.equal(requested, false, 'stale input must be rejected before requesting approval');
  });
}

test('approval cannot survive changes while awaiting an answer', options, async t => {
  const f = await fixture(t);
  await f.evaluate();
  await assert.rejects(f.controller.adopt({ authorize: async challenge => {
    assert.equal(challenge.action, 'adopt');
    await f.put('feedback/failure.txt', 'new evidence arrived during approval wait');
    return true;
  } }), { code: 'E_RSI_STALE' });
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD');
});

test('rollback refuses third-party edits and does not request permission to overwrite them', options, async t => {
  const f = await fixture(t);
  await f.evaluate();
  await f.controller.adopt({ authorize: async () => true });
  await f.put('strategy.txt', 'later user work');
  let requested = false;
  await assert.rejects(f.controller.rollback({ authorize: async () => { requested = true; return true; } }), { code: 'E_RSI_CONFLICT' });
  assert.equal(requested, false);
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'later user work');
});

test('candidate count, candidate bytes, and original recovery bytes are bounded', options, async t => {
  const f = await fixture(t);
  await assert.rejects(f.controller.propose({ ...f.candidate, files: Array.from({ length: 21 }, (_, i) => ({ path: `file-${i}`, content: 'x' })) }), { code: 'E_RSI_INVALID' });
  await assert.rejects(f.controller.propose({ ...f.candidate, files: [{ path: 'strategy.txt', content: 'x'.repeat(256 * 1024 + 1) }] }), { code: 'E_RSI_CANDIDATE_BUDGET' });
  await f.put('strategy.txt', 'x'.repeat(256 * 1024 + 1));
  await assert.rejects(f.controller.propose(f.candidate), { code: 'E_RSI_CANDIDATE_BUDGET' });
  assert.equal((await f.controller.inspect()).status, 'empty');
});

for (const resource of ['bytes', 'files']) {
  test(`aggregate input ${resource} budget cannot be bypassed by individually valid files`, options, async t => {
    const f = await fixture(t);
    const extra = Array.from({ length: resource === 'bytes' ? 9 : 125 }, (_, i) => `inputs/extra-${i}.txt`);
    for (const path of extra) await f.put(path, resource === 'bytes' ? 'x'.repeat(1024 * 1024) : 'x');
    await f.put('rsi-plan.json', JSON.stringify({ ...f.plan, inputs: [...f.plan.inputs, ...extra] }));
    await assert.rejects(f.controller.propose(f.candidate), { code: 'E_RSI_READ_BUDGET' });
    await assert.rejects(stat(join(f.root, f.config.statePath)), { code: 'ENOENT' });
  });
}

test('evaluation count budget stops additional commands without adding a record', options, async t => {
  const f = await fixture(t, { plan: { maxEvaluations: 1 } });
  const first = await f.evaluate();
  await assert.rejects(f.controller.evaluate(), { code: 'E_RSI_EVALUATION_BUDGET' });
  assert.equal((await f.controller.inspect()).evaluation.digest, first.evaluation.digest);
});

for (const resource of ['output', 'timeout']) {
  test(`${resource} failure is not an acceptable failing baseline`, options, async t => {
    const source = resource === 'output' ? "process.stdout.write('x'.repeat(4096));setInterval(()=>{},1000)" : 'setInterval(()=>{},1000)';
    const f = await fixture(t, { evaluator: source, plan: { timeoutMs: 200, maxOutputBytes: 1024 } });
    const evaluated = await f.evaluate();
    assert.equal(evaluated.evaluation.eligible, false);
    assert.equal(evaluated.evaluation.runs.length, 1);
    const baseline = evaluated.evaluation.runs[0];
    assert.equal(resource === 'output' ? baseline.outputExceeded : baseline.timedOut, true);
    assert.ok(Buffer.byteLength(baseline.stdout) + Buffer.byteLength(baseline.stderr) <= 1024);
    await assert.rejects(f.controller.adopt({ authorize: async () => true }), { code: 'E_RSI_NOT_ELIGIBLE' });
  });
}

test('proposal and evaluation digest tampering is rejected instead of trusting status', options, async t => {
  const f = await fixture(t);
  await f.evaluate();
  const saved = JSON.parse(await readFile(join(f.root, f.config.statePath), 'utf8'));
  for (const mutate of [
    s => { s.proposal.files[0].content = 'unapproved replacement'; },
    s => { s.evaluations[0].runs[0].exitCode = 0; },
    s => {
      const record = s.evaluations[0];
      record.runs[1].exitCode = 17;
      const { digest, ...unsealed } = record;
      record.digest = sha(JSON.stringify(unsealed)); // A consistent checksum still cannot rescue an inconsistent verdict.
    },
  ]) {
    const corrupted = structuredClone(saved);
    mutate(corrupted);
    await f.put(f.config.statePath, JSON.stringify(corrupted));
    await assert.rejects(f.controller.inspect(), { code: 'E_RSI_INVALID' });
    await assert.rejects(f.controller.adopt({ authorize: async () => true }), { code: 'E_RSI_INVALID' });
    assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD');
  }
});

test('cancellation after a real first-file adoption preserves intent and supports separately approved rollback', options, async t => {
  const f = await fixture(t, { plan: { inputs: ['strategy.txt', 'second.txt', 'rules.txt', 'evaluate.mjs'], targets: ['strategy.txt', 'second.txt'] } });
  await f.put('second.txt', 'before-second');
  await f.evaluate({ ...f.candidate, files: [...f.candidate.files, { path: 'second.txt', content: 'after-second' }] });
  const abort = new AbortController();
  const cancellation = new Error('fixture cancellation after first target rename');
  const originalRename = fileSystem.rename;
  let actualWrites = 0;
  const mock = t.mock.method(fileSystem, 'rename', async (from, to) => {
    await originalRename(from, to);
    if (String(to) === join(f.root, 'strategy.txt')) { actualWrites++; abort.abort(cancellation); }
  });
  syncBuiltinESMExports();
  try {
    await assert.rejects(f.controller.adopt({ authorize: async () => true, signal: abort.signal }), e => e === cancellation);
  } finally { mock.mock.restore(); syncBuiltinESMExports(); }
  assert.equal(actualWrites, 1);
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'GOOD');
  assert.equal(await readFile(join(f.root, 'second.txt'), 'utf8'), 'before-second');
  const reopened = await openRSI(f.config);
  const pending = await reopened.inspect();
  assert.equal(pending.status, 'applying');
  assert.equal(pending.next, 'reconcile');
  await assert.rejects(reopened.adopt({ authorize: async () => true }), { code: 'E_RSI_NOT_ELIGIBLE' });
  await assert.rejects(reopened.rollback(), { code: 'E_RSI_APPROVAL' });
  // Recovery remains possible even after the old forward authorization expires.
  await f.put('rsi-plan.json', JSON.stringify({ ...f.plan, revoked: true, expiresAt: '2000-01-01T00:00:00.000Z' }));
  const rolled = await reopened.rollback({ authorize: async challenge => {
    assert.equal(challenge.action, 'rollback');
    assert.equal(challenge.changes.length, 2);
    return true;
  } });
  assert.equal(rolled.status, 'rolled_back');
  assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD');
  assert.equal(await readFile(join(f.root, 'second.txt'), 'utf8'), 'before-second');
});

for (const expiry of ['approval', 'authority']) {
  test(`${expiry} expiry during locked revalidation refuses adoption before writing intent`, options, async t => {
    const initialTime = Date.now();
    const authorityExpiry = expiry === 'authority' ? initialTime + 60000 : Date.parse('2099-01-01T00:00:00.000Z');
    const f = await fixture(t, { plan: { expiresAt: new Date(authorityExpiry).toISOString() } });
    await f.evaluate();
    const stateFile = join(f.root, f.config.statePath);
    const before = await readFile(stateFile);
    let now = initialTime, protectionCalls = 0, approvalCalls = 0;
    const clock = t.mock.method(Date, 'now', () => now);
    try {
      const controller = await openRSI({ ...f.config, protectedPaths: async () => {
        protectionCalls++;
        if (protectionCalls === 4) {
          // The second prepare has passed its snapshot authority check. Advance
          // only now, after the external approval-expiry check and lock entry.
          now = expiry === 'approval' ? initialTime + 180001 : authorityExpiry + 1;
        }
        return [];
      } });
      await assert.rejects(controller.adopt({ authorize: async challenge => {
        approvalCalls++;
        assert.equal(protectionCalls, 2, 'initial prepare checks protection in snapshot and again before its challenge');
        assert.ok(Date.now() < Date.parse(challenge.expiresAt));
        assert.ok(Date.now() < Date.parse(challenge.authorityExpiresAt));
        return true;
      } }), { code: expiry === 'approval' ? 'E_RSI_APPROVAL' : 'E_RSI_AUTHORITY' });
      assert.equal(approvalCalls, 1);
      assert.equal(protectionCalls, 4, 'expiry must be detected after both protection checks of the locked prepare');
      assert.deepEqual(await readFile(stateFile), before);
      assert.equal(await readFile(join(f.root, 'strategy.txt'), 'utf8'), 'BAD');
    } finally { clock.mock.restore(); }
    assert.equal((await f.controller.inspect()).status, 'evaluated');
  });
}

test('RSI inspect leaves both absent and existing state unchanged including mtime', options, async t => {
  const f = await fixture(t);
  const stateFile = join(f.root, f.config.statePath);
  assert.equal((await f.controller.inspect()).status, 'empty');
  await assert.rejects(stat(stateFile), { code: 'ENOENT' });
  await f.evaluate();
  const fixedTime = new Date('2000-01-01T00:00:00.000Z');
  await utimes(stateFile, fixedTime, fixedTime);
  const before = await readFile(stateFile);
  const beforeMtime = (await stat(stateFile)).mtimeMs;
  for (let i = 0; i < 2; i++) {
    const inspected = await f.controller.inspect();
    assert.equal(inspected.next, 'human_approval');
    assert.ok(inspected.io.filesRead > 0 && inspected.io.bytesRead > 0);
  }
  assert.deepEqual(await readFile(stateFile), before);
  assert.equal((await stat(stateFile)).mtimeMs, beforeMtime);
});

test('RSI evaluation resource diagnostic records two real commands and scoped logical reads', options, async t => {
  const f = await fixture(t);
  await f.controller.propose(f.candidate);
  // Fixture creation and the original failure command are outside this sample.
  const cpuBefore = process.cpuUsage();
  const wallBefore = process.hrtime.bigint();
  const evaluated = await f.controller.evaluate();
  const wallMs = Number(process.hrtime.bigint() - wallBefore) / 1e6;
  const cpu = process.cpuUsage(cpuBefore);
  assert.equal(evaluated.evaluation.eligible, true);
  assert.deepEqual(evaluated.evaluation.runs.map(run => [run.kind, run.exitCode]), [['baseline', 3], ['candidate', 0]]);
  assert.ok(evaluated.io.filesRead > 0 && evaluated.io.bytesRead > 0);
  for (const run of evaluated.evaluation.runs) {
    assert.equal(run.protection, true);
    assert.equal(run.ioBefore.filesRead, f.plan.inputs.length);
    assert.deepEqual(run.ioBefore, run.ioAfter);
    assert.ok(run.durationMs >= 0);
  }
  t.diagnostic(JSON.stringify({
    measurement: 'one isolated RSI comparison; logical input/scan reads, not physical IO or production savings',
    environment: { node: process.version, os: platform(), release: release(), architecture: arch() },
    input: { declaredInputs: f.plan.inputs.length, authorityFiles: f.plan.authority.length, candidateFiles: f.candidate.files.length },
    wallMs: Number(wallMs.toFixed(3)),
    parentProcessCpuMs: { user: cpu.user / 1000, system: cpu.system / 1000 },
    cpuScope: 'process.cpuUsage measures the parent test process, not evaluator child-process CPU',
    reportedInputReads: evaluated.io,
    inputReadScope: 'operation-wide adapter counter including source rechecks and scans; per-run scan counters below are subsets, not additive',
    runs: evaluated.evaluation.runs.map(run => ({ kind: run.kind, exitCode: run.exitCode,
      commandWallMs: run.durationMs, scanBefore: run.ioBefore, scanAfter: run.ioAfter,
      capturedOutputBytes: Buffer.byteLength(run.stdout) + Buffer.byteLength(run.stderr) })),
  }));
});

test('fixed evaluator entry remains protected even if mistakenly listed as a candidate target', options, async t => {
  const f = await fixture(t);
  for (const entry of ['evaluate.mjs', './evaluate.mjs', join(f.root, 'evaluate.mjs')]) {
    await f.put('rsi-plan.json', JSON.stringify({ ...f.plan, targets: ['strategy.txt', 'evaluate.mjs'], command: [process.execPath, entry] }));
    await assert.rejects(f.controller.propose({ ...f.candidate, files: [{ path: 'evaluate.mjs', content: 'process.exit(0)' }] }), { code: 'E_RSI_PROTECTED' });
    await assert.rejects(stat(join(f.root, f.config.statePath)), { code: 'ENOENT' });
    assert.equal(await readFile(join(f.root, 'evaluate.mjs'), 'utf8'), evaluator);
  }
});

test('candidate and feedback paths cannot escape the admitted root or target Git internals', options, async t => {
  const f = await fixture(t);
  for (const path of ['../outside', '/tmp/absolute-escape', '.git/config', 'nested/../escape']) {
    await assert.rejects(f.controller.propose({ ...f.candidate, files: [{ path, content: 'bad' }] }), { code: 'E_RSI_INVALID' });
  }
  await assert.rejects(f.controller.propose({ ...f.candidate, feedback: [{ path: '../outside', kind: 'failure' }] }), { code: 'E_RSI_INVALID' });
  assert.equal((await f.controller.inspect()).status, 'empty');
});

test('symlink evaluation inputs are refused before proposal persistence or command execution', options, async t => {
  const f = await fixture(t);
  await rm(join(f.root, 'rules.txt'));
  await symlink(join(f.root, 'authority.md'), join(f.root, 'rules.txt'));
  await assert.rejects(f.controller.propose(f.candidate), { code: 'E_RSI_INVALID' });
  await assert.rejects(stat(join(f.root, f.config.statePath)), { code: 'ENOENT' });
});

test('a candidate evaluator cannot pass after adding an unlisted file to its workspace', options, async t => {
  const source = evaluator.replace("if(actual==='GOOD')", "if(actual==='GOOD'){(await import('node:fs')).writeFileSync('unexpected.txt','new asset');}\nif(actual==='GOOD')");
  const f = await fixture(t, { evaluator: source });
  const evaluated = await f.evaluate();
  assert.equal(evaluated.evaluation.runs[1].exitCode, 0);
  assert.equal(evaluated.evaluation.runs[1].protection, false);
  assert.equal(evaluated.evaluation.eligible, false);
  await assert.rejects(f.controller.adopt({ authorize: async () => true }), { code: 'E_RSI_NOT_ELIGIBLE' });
  await assert.rejects(stat(join(f.root, 'unexpected.txt')), { code: 'ENOENT' });
});

test('shared evaluation read budget includes later workspace scans instead of resetting per phase', options, async t => {
  const f = await fixture(t, { plan: { inputs: ['strategy.txt', 'rules.txt', 'evaluate.mjs', 'large-one.txt', 'large-two.txt'] } });
  await f.put('large-one.txt', 'a'.repeat(1024 * 1024));
  await f.put('large-two.txt', 'b'.repeat(1024 * 1024));
  const evaluated = await f.evaluate();
  assert.equal(evaluated.evaluation.eligible, false);
  assert.ok(evaluated.evaluation.error === 'E_RSI_READ_BUDGET' || evaluated.evaluation.runs.some(run => run.protectionError === 'E_RSI_READ_BUDGET'));
  assert.ok(evaluated.io.bytesRead >= 6 * 1024 * 1024, 'count must include completed later phases, not only the source snapshot');
  assert.ok(evaluated.io.bytesRead <= 8 * 1024 * 1024);
  assert.ok(evaluated.io.filesRead <= 128);
  await assert.rejects(f.controller.adopt({ authorize: async () => true }), { code: 'E_RSI_NOT_ELIGIBLE' });
});

test('historical adopted and rolled-back statuses do not hide external restoration of a known target version', options, async t => {
  const f = await fixture(t);
  await f.evaluate();
  await f.controller.adopt({ authorize: async () => true });
  await f.put('strategy.txt', 'BAD');
  const restoredOriginal = await f.controller.inspect();
  assert.equal(restoredOriginal.status, 'adopted');
  assert.equal(restoredOriginal.targetState, 'original');
  assert.equal(restoredOriginal.next, 'reconcile');
  await f.controller.rollback({ authorize: async () => true });
  await f.put('strategy.txt', 'GOOD');
  const restoredCandidate = await f.controller.inspect();
  assert.equal(restoredCandidate.status, 'rolled_back');
  assert.equal(restoredCandidate.targetState, 'candidate');
  assert.equal(restoredCandidate.next, 'reconcile');
});
