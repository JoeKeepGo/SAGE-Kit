// Optional, bounded RSI. Project authority selects inputs and commands; a host
// supplies human approval or a preauthorized project policy. Temporary evaluation
// directories are isolation, not a sandbox.
import { open, lstat, realpath, mkdir, rename, unlink, mkdtemp, rm, opendir } from 'node:fs/promises';
import { resolve, dirname, join, isAbsolute } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash, randomUUID } from 'node:crypto';
import { runFixed } from './rsi-process.mjs';

const hash = value => createHash('sha256').update(value).digest('hex');
const digest = value => hash(JSON.stringify(value));
const error = (code, message) => Object.assign(new Error(message), { code });
const require = (ok, message, code = 'E_RSI_INVALID') => { if (!ok) throw error(code, message); };
const object = x => x && typeof x === 'object' && !Array.isArray(x);
const text = x => typeof x === 'string' && x.trim().length > 0 && x.length <= 4096;
const pathName = x => text(x) && !isAbsolute(x) && !/[\\:\0]/.test(x) && x.split('/').length <= 32 && x.split('/').every(p => p && !['.', '..', '.git'].includes(p.toLowerCase()));
const list = (x, test = pathName) => Array.isArray(x) && x.length > 0 && x.length <= 128 && x.every(test) && new Set(x).size === x.length;
const abort = signal => signal?.throwIfAborted();
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const LIMIT = 8 * 1024 * 1024, STATE_LIMIT = 2 * 1024 * 1024, CHANGE_LIMIT = 256 * 1024;
const withoutDigest = ({ digest: ignored, ...rest }) => rest;
const seal = value => ({ ...value, digest: digest(value) });
const validSeal = value => object(value) && value.digest === digest(withoutDigest(value));
const currentRecord = s => s.evaluations.at(-1);
const sha256 = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const cleanRun = r => r && Number.isInteger(r.exitCode) && r.exitCode >= 0 && !r.timedOut && !r.cancelled && !r.outputExceeded;
const goodRun = r => r && r.protection === true && Number.isInteger(r.exitCode) && r.exitCode >= 0 && r.timedOut === false && r.cancelled === false && r.outputExceeded === false;
const eligible = e => e?.complete === true && !e.error && e.runs?.length === 2 && e.runs[0].kind === 'baseline' && e.runs[1].kind === 'candidate' && e.runs.every(goodRun) && e.runs[1].exitCode === 0;

function validateAutomaticPolicy(value) {
  const branch = b => text(b) && /^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(b) && !b.includes('..') && !b.endsWith('/') && !b.endsWith('.lock');
  require(object(value) && Object.keys(value).every(k => ['branch', 'baseBranch', 'planSha256', 'maxRounds', 'improvement'].includes(k)), 'Invalid automatic policy', 'E_RSI_POLICY');
  const p = structuredClone(value), rule = p.improvement;
  require(branch(p.branch) && branch(p.baseBranch) && p.branch !== p.baseBranch && !/^(main|master|trunk|develop|development|release)(\/|$)/i.test(p.branch) && sha256(p.planSha256) && Number.isInteger(p.maxRounds) && p.maxRounds >= 1 && p.maxRounds <= 3, 'Invalid automatic policy branch or bounds', 'E_RSI_POLICY');
  require(object(rule) && (rule.kind === 'repair' && Object.keys(rule).length === 1 || rule.kind === 'metric' && Object.keys(rule).every(k => ['kind', 'name', 'direction', 'minDelta'].includes(k)) && typeof rule.name === 'string' && /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(rule.name) && ['increase', 'decrease'].includes(rule.direction) && Number.isFinite(rule.minDelta) && rule.minDelta > 0), 'Invalid improvement rule', 'E_RSI_POLICY');
  return { branch: p.branch, baseBranch: p.baseBranch, planSha256: p.planSha256, maxRounds: p.maxRounds, improvement: rule.kind === 'repair' ? { kind: 'repair' } : { kind: 'metric', name: rule.name, direction: rule.direction, minDelta: rule.minDelta } };
}
function metric(run, rule) {
  try { const value = JSON.parse(run.stdout); return object(value?.metrics) && Object.hasOwn(value.metrics, rule.name) && Number.isFinite(value.metrics[rule.name]) ? value.metrics[rule.name] : null; }
  catch { return null; }
}
function improvement(record, rule) {
  const [before, after] = record.runs;
  if (rule.kind === 'repair') return { kind: 'repair', passed: eligible(record) && before.exitCode > 0 };
  const baseline = metric(before ?? {}, rule), candidate = metric(after ?? {}, rule);
  const delta = baseline === null || candidate === null ? null : (candidate - baseline) * (rule.direction === 'increase' ? 1 : -1);
  return { kind: 'metric', name: rule.name, baseline, candidate, delta, passed: eligible(record) && before.exitCode === 0 && delta !== null && delta >= rule.minDelta };
}

async function safe(root, name, signal) {
  require(pathName(name), 'Unsafe relative path');
  let path = root;
  for (const part of name.split('/')) {
    abort(signal); path = join(path, part);
    try { require(!(await lstat(path)).isSymbolicLink(), 'Symlink path refused'); }
    catch (cause) { if (cause.code !== 'ENOENT') throw cause; }
  }
  return path;
}
function reader(root, signal, io = { filesRead: 0, bytesRead: 0 }) {
  const cache = new Map();
  async function file(name, limit = 1024 * 1024, missing = false) {
    abort(signal);
    if (cache.has(name)) return cache.get(name);
    require(io.filesRead < 128, 'RSI file budget exceeded', 'E_RSI_READ_BUDGET');
    const path = await safe(root, name, signal);
    let handle;
    try {
      const info = await lstat(path);
      require(info.isFile() && info.size <= limit, 'Expected bounded regular file', 'E_RSI_READ_BUDGET');
      handle = await open(path, 'r');
    }
    catch (cause) { if (missing && cause.code === 'ENOENT') { cache.set(name, null); return null; } throw cause; }
    try {
      const stat = await handle.stat();
      require(stat.isFile() && stat.size <= limit, 'Expected bounded regular file', 'E_RSI_READ_BUDGET');
      require(io.bytesRead + stat.size <= LIMIT, 'RSI total read budget exceeded', 'E_RSI_READ_BUDGET');
      const data = Buffer.alloc(stat.size + 1); let offset = 0;
      io.filesRead++;
      while (offset < data.length) {
        abort(signal);
        const { bytesRead } = await handle.read(data, offset, Math.min(65536, data.length - offset), null);
        abort(signal); if (!bytesRead) break;
        offset += bytesRead; io.bytesRead += bytesRead;
        require(offset <= stat.size && io.bytesRead <= LIMIT, 'File grew or read budget exceeded', 'E_RSI_READ_BUDGET');
      }
      require(offset === stat.size, 'File changed during read');
      const bytes = data.subarray(0, offset);
      const value = { bytes, sha256: hash(bytes), mode: stat.mode & 0o777 };
      cache.set(name, value); return value;
    } finally { await handle.close(); }
  }
  return { file, io };
}
const identity = f => f ? { sha256: f.sha256, mode: f.mode } : null;
async function atomic(path, bytes, mode = 0o600, signal) {
  require(bytes.length <= STATE_LIMIT, 'RSI write budget exceeded', 'E_RSI_STATE_BUDGET');
  abort(signal);
  await mkdir(dirname(path), { recursive: true });
  const temp = `${path}.${randomUUID()}.tmp`; let handle;
  try {
    handle = await open(temp, 'wx', mode); await handle.chmod(mode); await handle.writeFile(bytes); await handle.sync();
    await handle.close(); handle = undefined; abort(signal); await rename(temp, path);
  } finally {
    await handle?.close(); await unlink(temp).catch(cause => { if (cause.code !== 'ENOENT') throw cause; });
  }
}
async function scan(root, signal, budget) {
  const result = {}; let entries = 0;
  const read = reader(root, signal, budget), start = { ...read.io };
  async function walk(dir = '') {
    abort(signal);
    const directory = await opendir(join(root, dir));
    for await (const entry of directory) {
      require(++entries <= 256, 'Workspace entry budget exceeded', 'E_RSI_READ_BUDGET');
      const name = entry.name;
      const rel = dir ? dir + '/' + name : name;
      const path = await safe(root, rel, signal), stat = await lstat(path);
      require(!stat.isSymbolicLink(), 'Workspace symlink refused');
      if (stat.isDirectory()) { result[rel + '/'] = { directory: true, mode: stat.mode & 0o777 }; await walk(rel); }
      else result[rel] = identity(await read.file(rel));
    }
  }
  await walk(); return { manifest: Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b))), io: { filesRead: read.io.filesRead - start.filesRead, bytesRead: read.io.bytesRead - start.bytesRead } };
}

export async function openRSI({ root, planPath, statePath, protectedPaths = async () => [], automaticPolicy }) {
  const policy = automaticPolicy === undefined ? undefined : validateAutomaticPolicy(automaticPolicy);
  const policyDigest = policy ? digest(policy) : undefined;
  const base = await realpath(root);
  require(pathName(planPath) && pathName(statePath) && planPath !== statePath, 'Invalid RSI paths');
  const stateFile = await safe(base, statePath);
  require(typeof protectedPaths === 'function', 'Host protection resolver must be a function');
  async function protections(paths, signal) {
    const supplied = await protectedPaths({ signal });
    const protectedList = Array.isArray(supplied) ? supplied : supplied?.paths;
    require(Array.isArray(supplied) || object(supplied) && Object.keys(supplied).every(k => ['paths', 'binding'].includes(k)) && sha256(supplied.binding), 'Invalid host authority binding');
    require(Array.isArray(protectedList) && protectedList.length <= 128 && protectedList.every(pathName), 'Invalid host protection set');
    require(paths.every(path => !protectedList.some(p => path === p || path.startsWith(p + '/'))), 'RSI cannot change current host governance or control records', 'E_RSI_PROTECTED');
    const normalized = [...new Set(protectedList)].sort();
    return Array.isArray(supplied) ? normalized : { paths: normalized, binding: supplied.binding };
  }
  async function save(state) { if (state.automatic) state.automatic = seal(withoutDigest(state.automatic)); await safe(base, statePath); await atomic(stateFile, Buffer.from(JSON.stringify(state, null, 2) + '\n')); }
  async function locked(fn) {
    const lock = await safe(base, statePath + '.lock'); await mkdir(dirname(lock), { recursive: true });
    let handle;
    try { handle = await open(lock, 'wx'); } catch (cause) { if (cause.code === 'EEXIST') throw error('E_RSI_LOCKED', 'RSI writer is active or requires explicit lock recovery'); throw cause; }
    try { return await fn(); } finally { await handle.close(); await unlink(lock); }
  }
  async function load(read) {
    const raw = await read.file(statePath, STATE_LIMIT, true);
    if (!raw) return null;
    const s = JSON.parse(raw.bytes.toString('utf8'));
    validateState(s); return s;
  }
  function validateState(s, archived = false) {
    require(s.version === 1 && ['proposed', 'evaluating', 'evaluated', 'applying', 'verifying', 'observing', 'adopted', 'rolling_back', 'rolled_back'].includes(s.status), 'Invalid RSI state');
    require(validSeal(s.proposal) && Array.isArray(s.evaluations) && s.evaluations.length <= 3, 'Invalid proposal/evaluation binding');
    validateCandidate(s.proposal);
    require(Array.isArray(s.proposal.originals) && s.proposal.originals.length === s.proposal.files.length && s.proposal.originals.every((f, i) => f.path === s.proposal.files[i].path && (f.content === null || typeof f.content === 'string') && Number.isInteger(f.mode)), 'Invalid recovery materials');
    require(Buffer.byteLength(JSON.stringify(s.proposal.originals)) <= CHANGE_LIMIT + 16384, 'Recovery materials exceed budget');
    for (const e of s.evaluations) {
      require(validSeal(e) && e.proposalDigest === s.proposal.digest && typeof e.complete === 'boolean', 'Invalid evaluation digest');
      require(e.eligible === eligible(e), 'Inconsistent evaluation verdict');
    }
    if (['applying', 'verifying', 'observing', 'adopted', 'rolling_back', 'rolled_back'].includes(s.status)) {
      require(validSeal(s.approval) && s.approval.proposalDigest === s.proposal.digest && s.approval.evaluationDigest === currentRecord(s)?.digest && eligible(currentRecord(s)), 'Invalid adoption approval binding');
    }
    if (s.automatic) {
      const a = s.automatic;
      require(!archived && validSeal(a) && sha256(a.policyDigest) && sha256(a.frozenDigest) && sha256(a.targetDigest) && text(a.branch) && /^[a-f0-9]{40,64}$/.test(a.head) && /^[a-f0-9]{40,64}$/.test(a.anchorHead) && Number.isInteger(a.round) && a.round >= 1 && a.round <= 3 && Number.isInteger(a.maxRounds) && a.round <= a.maxRounds && a.maxRounds <= 3 && Number.isInteger(a.consecutiveFailures) && a.consecutiveFailures >= 0 && a.consecutiveFailures <= 3 && Number.isInteger(a.failuresAtStart) && a.failuresAtStart >= 0 && a.failuresAtStart <= 2 && Array.isArray(a.history) && a.history.length === a.round - 1, 'Invalid automatic policy state');
      for (const [i, item] of a.history.entries()) { require(validSeal(item) && item.round === i + 1 && !item.state?.automatic, 'Invalid automatic round history'); validateState(item.state, true); }
      if (s.approval) require(s.approval.source === 'preauthorized-project-policy' && s.approval.policyDigest === a.policyDigest && s.approval.branch === a.branch && s.approval.head === a.head, 'Invalid automatic adoption receipt');
    }
    if (s.postchecks) require(Array.isArray(s.postchecks) && s.postchecks.length <= 4 && s.postchecks.every(p => validSeal(p) && p.proposalDigest === s.proposal.digest && p.evaluationDigest === currentRecord(s)?.digest && typeof p.passed === 'boolean' && p.protection === true && (!p.passed || cleanRun(p.run) && p.run.exitCode === 0)), 'Invalid bounded postcheck history');
    if (s.approval?.source === 'preauthorized-project-policy') {
      require(currentRecord(s)?.improvement?.passed === true, 'Automatic approval lacks measured improvement');
      if (s.status === 'adopted') require(s.postchecks?.at(-1)?.passed === true, 'Automatic adoption lacks successful postcheck');
      if (s.status === 'rolled_back') require(validSeal(s.rollbackApproval) && s.rollbackApproval.source === 'preauthorized-project-policy' && s.rollbackApproval.policyDigest === s.approval.policyDigest && s.rollbackApproval.proposalDigest === s.proposal.digest && s.rollbackApproval.evaluationDigest === currentRecord(s).digest, 'Invalid automatic rollback receipt');
    }
  }
  function validateCandidate(p) {
    require(text(p.hypothesis) && Array.isArray(p.feedback) && p.feedback.length > 0 && p.feedback.length <= 20 && p.feedback.every(f => object(f) && pathName(f.path) && ['failure', 'review', 'rework'].includes(f.kind)), 'Invalid feedback/hypothesis');
    require(Array.isArray(p.files) && p.files.length > 0 && p.files.length <= 20 && new Set(p.files.map(f => f.path)).size === p.files.length && p.files.every(f => object(f) && pathName(f.path) && (typeof f.content === 'string' || f.content === null)), 'Invalid candidate files');
    require(p.files.reduce((n, f) => n + Buffer.byteLength(f.content ?? ''), 0) <= CHANGE_LIMIT, 'Candidate byte budget exceeded', 'E_RSI_CANDIDATE_BUDGET');
  }
  async function snapshot(read, proposal, signal) {
    const planFile = await read.file(planPath, 65536), p = JSON.parse(planFile.bytes.toString('utf8'));
    require(p.version === 1 && list(p.authority) && list(p.inputs) && list(p.targets) && p.targets.every(t => p.inputs.includes(t)) && p.targets.every(t => !p.authority.includes(t)), 'Invalid RSI input/target authority');
    require([...p.authority, ...p.inputs].every(t => t !== statePath && t !== planPath && t !== statePath + '.lock'), 'Control records must be separate');
    const hostProtected = await protections(p.targets, signal);
    require(Array.isArray(p.command) && p.command.length > 0 && p.command.length <= 32 && p.command.every(text) && isAbsolute(p.command[0]), 'Fixed command must use an absolute executable');
    require(p.targets.every(t => !p.command.includes(t) && !p.command.includes('./' + t) && !p.command.includes(resolve(base, t))), 'The fixed evaluator entry cannot be a candidate target', 'E_RSI_PROTECTED');
    require(Number.isInteger(p.maxEvaluations) && p.maxEvaluations >= 1 && p.maxEvaluations <= 3 && Number.isInteger(p.timeoutMs) && p.timeoutMs >= 100 && p.timeoutMs <= 60000 && Number.isInteger(p.maxOutputBytes) && p.maxOutputBytes >= 1024 && p.maxOutputBytes <= 65536 && typeof p.revoked === 'boolean' && Number.isFinite(Date.parse(p.expiresAt)), 'Invalid RSI budget');
    require(!p.revoked && Date.now() < Date.parse(p.expiresAt), 'RSI authorization revoked or expired', 'E_RSI_AUTHORITY');
    const files = new Map(), authority = {}, inputs = {}, feedback = [];
    for (const name of [...new Set([...p.authority, ...p.inputs])].sort()) {
      const value = await read.file(name, 1024 * 1024, p.targets.includes(name)); files.set(name, value);
      if (p.authority.includes(name)) authority[name] = identity(value);
      if (p.inputs.includes(name)) inputs[name] = identity(value);
    }
    for (const ref of proposal.feedback) {
      require(![planPath, statePath, statePath + '.lock'].includes(ref.path) && !p.targets.includes(ref.path), 'Feedback must be separate from mutable controls/targets');
      feedback.push({ path: ref.path, kind: ref.kind, ...identity(await read.file(ref.path)) });
    }
    // Bind the selected executable's observed identity without repeatedly hashing
    // a potentially large toolchain. External dependencies are not attested here.
    abort(signal); const executable = await realpath(p.command[0]), stat = await lstat(executable);
    require(stat.isFile(), 'Evaluator executable is not a regular file');
    const runtime = { executable, size: stat.size, mtimeMs: stat.mtimeMs, mode: stat.mode };
    const fingerprint = digest({ plan: hash(planFile.bytes), authority, inputs, feedback, runtime, hostProtected });
    const frozenDigest = digest({ plan: hash(planFile.bytes), authority, inputs: Object.fromEntries(Object.entries(inputs).filter(([path]) => !p.targets.includes(path))), runtime, hostProtected });
    const targetDigest = digest(Object.fromEntries(p.targets.map(path => [path, inputs[path]])));
    return { plan: p, planSha256: hash(planFile.bytes), files, inputs, feedback, fingerprint, frozenDigest, targetDigest, runtime };
  }
  function summary(s, io) {
    if (!s) return { status: 'empty', next: 'propose', io };
    const evaluation = currentRecord(s);
    const result = { status: s.status, next: s.status === 'proposed' ? 'evaluate' : s.status === 'evaluating' || ['applying', 'rolling_back'].includes(s.status) ? 'reconcile' : s.status === 'evaluated' ? (evaluation?.eligible ? 'human_approval' : 'review_failure') : s.status === 'adopted' ? 'observe_or_rollback' : 'complete', proposal: s.proposal, ...(evaluation ? { evaluation } : {}), ...(s.approval ? { approval: s.approval } : {}), io };
    if (s.automatic) {
      const { history, digest: ignored, ...automatic } = s.automatic;
      result.automatic = { ...automatic, history: history.map(h => ({ round: h.round, status: h.state.status, proposalDigest: h.state.proposal.digest, evaluationDigest: currentRecord(h.state)?.digest })) };
      if (['evaluating', 'applying', 'verifying', 'observing', 'rolling_back'].includes(s.status) || s.status === 'evaluated' && !s.automatic.lastOutcome) result.next = 'reconcile';
      else if (s.automatic.stopReason) result.next = 'stop';
      else if (s.status !== 'proposed') result.next = 'continue_propose';
      if (s.postchecks) result.postchecks = s.postchecks;
    }
    return result;
  }
  async function assertSource(read, s, signal) {
    const snap = await snapshot(read, s.proposal, signal);
    require(snap.fingerprint === s.proposal.fingerprint, 'RSI inputs changed; prepare and evaluate a new round', 'E_RSI_STALE');
    return snap;
  }
  async function gitIdentity(signal, anchorHead, io) {
    require(policy, 'Automatic policy is required', 'E_RSI_POLICY');
    async function git(args, allowOne = false) {
      require((io.gitCommands ?? 0) < 32, 'Git command budget exceeded', 'E_RSI_GIT_BUDGET'); io.gitCommands = (io.gitCommands ?? 0) + 1;
      const r = await runFixed(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '--no-optional-locks', ...args], { cwd: base, timeoutMs: 2000, maxOutputBytes: 4096, signal });
      require(cleanRun(r) && (r.exitCode === 0 || allowOne && r.exitCode === 1), 'Bounded Git identity check failed', 'E_RSI_GIT');
      return r;
    }
    const top = (await git(['rev-parse', '--show-toplevel'])).stdout.trim();
    require(await realpath(top) === base, 'Automatic policy requires the exact repository root', 'E_RSI_GIT');
    const branch = (await git(['symbolic-ref', '--quiet', '--short', 'HEAD'])).stdout.trim();
    require(branch === policy.branch, 'Automatic policy branch changed', 'E_RSI_BRANCH');
    const head = (await git(['rev-parse', '--verify', 'HEAD'])).stdout.trim();
    anchorHead ??= (await git(['rev-parse', '--verify', 'refs/heads/' + policy.baseBranch])).stdout.trim();
    require(/^[a-f0-9]{40,64}$/.test(head) && /^[a-f0-9]{40,64}$/.test(anchorHead), 'Invalid Git revision', 'E_RSI_GIT');
    require((await git(['merge-base', '--is-ancestor', anchorHead, head], true)).exitCode === 0, 'Approved base is not an ancestor of this branch', 'E_RSI_BRANCH');
    return { branch, head, anchorHead };
  }
  async function autoContext(s, read, signal, nextRound = false) {
    require(policy && s.automatic?.policyDigest === policyDigest, 'Automatic policy changed or unavailable', 'E_RSI_POLICY');
    const snap = await snapshot(read, s.proposal, signal);
    require(snap.planSha256 === policy.planSha256 && snap.frozenDigest === s.automatic.frozenDigest, 'Approved plan or protected inputs changed', 'E_RSI_STALE');
    require(snap.targetDigest === s.automatic.targetDigest, 'Targets changed outside this round; explicit reconciliation required', 'E_RSI_CONFLICT');
    require(nextRound || same(snap.feedback, s.proposal.feedback), 'Bound feedback changed', 'E_RSI_STALE');
    const git = await gitIdentity(signal, s.automatic.anchorHead, read.io);
    require(nextRound || git.head === s.automatic.head, 'Git HEAD changed during this round', 'E_RSI_STALE');
    return snap;
  }
  function failRound(s, reason) {
    s.automatic.consecutiveFailures = s.automatic.failuresAtStart + 1;
    s.automatic.lastOutcome = reason;
    if (s.automatic.consecutiveFailures >= 2) s.automatic.stopReason = 'consecutive_failures';
    else if (s.automatic.round >= policy.maxRounds) s.automatic.stopReason = 'max_rounds';
  }
  function targetDigestFor(s, snap, action) {
    const expected = { ...snap.inputs };
    for (const [i, file] of s.proposal.files.entries()) {
      const original = s.proposal.originals[i], content = action === 'adopt' ? file.content : original.content;
      expected[file.path] = content === null ? null : { sha256: hash(Buffer.from(content)), mode: original.mode };
    }
    return digest(Object.fromEntries(snap.plan.targets.map(path => [path, expected[path]])));
  }
  function receipt(s, action) {
    return seal({ source: 'preauthorized-project-policy', action, policyDigest, branch: s.automatic.branch, head: s.automatic.head, proposalDigest: s.proposal.digest, evaluationDigest: currentRecord(s).digest, decidedAt: new Date().toISOString() });
  }
  async function writeAutomatic(s, snap, action, io, signal) {
    for (const [i, f] of s.proposal.files.entries()) {
      abort(signal);
      require(Date.now() < Date.parse(snap.plan.expiresAt), 'RSI authorization expired during application', 'E_RSI_AUTHORITY');
      const read = reader(base, signal, io), now = identity(await read.file(f.path, CHANGE_LIMIT, true));
      require(same(now, snap.inputs[f.path]), 'Target changed before write; reconciliation required', 'E_RSI_CONFLICT');
      const original = s.proposal.originals[i], content = action === 'adopt' ? f.content : original.content;
      const path = await safe(base, f.path, signal);
      if (content === null) await unlink(path).catch(cause => { if (cause.code !== 'ENOENT') throw cause; });
      else await atomic(path, Buffer.from(content), original.mode, signal);
    }
    s.automatic.targetDigest = targetDigestFor(s, snap, action);
  }
  async function automaticRollback(s, io, signal, reason) {
    const snap = await autoContext(s, reader(base, signal, io), signal);
    s.rollbackApproval = receipt(s, 'rollback'); s.status = 'rolling_back'; await save(s);
    await writeAutomatic(s, snap, 'rollback', io, signal);
    await autoContext(s, reader(base, signal, io), signal);
    s.status = 'rolled_back'; failRound(s, reason); await save(s);
  }
  async function postcheck(s, io, signal, kind) {
    require((s.postchecks?.length ?? 0) < 4, 'Explicit observation budget exhausted', 'E_RSI_OBSERVATION_BUDGET');
    const snap = await autoContext(s, reader(base, signal, io), signal);
    s.status = kind === 'adoption' ? 'verifying' : 'observing'; await save(s);
    const run = await runFixed(snap.plan.command, { cwd: base, timeoutMs: snap.plan.timeoutMs, maxOutputBytes: snap.plan.maxOutputBytes, signal });
    abort(signal);
    // A changed authority, HEAD or target is a conflict, not permission to restore over it.
    await autoContext(s, reader(base, signal, io), signal);
    let passed = cleanRun(run) && run.exitCode === 0;
    if (policy.improvement.kind === 'metric') {
      const value = metric(run, policy.improvement), expected = currentRecord(s).improvement.candidate;
      passed &&= value !== null && (policy.improvement.direction === 'increase' ? value >= expected : value <= expected);
    }
    (s.postchecks ??= []).push(seal({ kind, proposalDigest: s.proposal.digest, evaluationDigest: currentRecord(s).digest, run, passed, protection: true }));
    if (!passed) { await automaticRollback(s, io, signal, 'postcheck_failed'); return; }
    s.status = 'adopted'; s.automatic.consecutiveFailures = 0; s.automatic.lastOutcome = 'adopted';
    if (s.automatic.round >= policy.maxRounds) s.automatic.stopReason = 'max_rounds';
    await save(s);
  }
  async function automaticAdopt(s, io, signal) {
    const snap = await autoContext(s, reader(base, signal, io), signal);
    require(snap.fingerprint === s.proposal.fingerprint && improvement(currentRecord(s), policy.improvement).passed, 'Automatic adoption requires bound real improvement', 'E_RSI_NOT_ELIGIBLE');
    s.approval = receipt(s, 'adopt'); s.status = 'applying'; await save(s);
    await writeAutomatic(s, snap, 'adopt', io, signal);
    await postcheck(s, io, signal, 'adoption');
    return summary(s, io);
  }
  async function observe({ signal } = {}) {
    if (!policy) return inspect({ signal });
    return locked(async () => {
      const read = reader(base, signal), s = await load(read);
      require(s?.automatic && s.status === 'adopted', 'Observation requires a settled automatic adoption', 'E_RSI_RECONCILE');
      await postcheck(s, read.io, signal, 'observation'); return summary(s, read.io);
    });
  }
  async function propose(input, { signal } = {}) {
    validateCandidate(input);
    require(Object.keys(input).every(k => ['hypothesis', 'feedback', 'files'].includes(k)), 'Unexpected candidate field');
    return locked(async () => {
      const read = reader(base, signal);
      const previous = await load(read);
      require(!previous || policy, 'This RSI round already has a candidate');
      let automatic;
      if (previous) {
        require(previous.automatic && ['adopted', 'rolled_back', 'evaluated'].includes(previous.status) && (previous.status !== 'evaluated' || previous.automatic.lastOutcome), 'Previous automatic round requires reconciliation', 'E_RSI_RECONCILE');
        require(!previous.automatic.stopReason && previous.automatic.round < policy.maxRounds && previous.automatic.consecutiveFailures < 2, 'Automatic policy window is exhausted', 'E_RSI_AUTO_STOP');
        await autoContext(previous, reader(base, signal, read.io), signal, true);
      }
      const snap = await snapshot(read, input, signal);
      require(input.files.every(f => snap.plan.targets.includes(f.path)), 'Candidate touches protected or unadmitted path', 'E_RSI_PROTECTED');
      let bytes = 0;
      const originals = input.files.map(f => {
        const original = snap.files.get(f.path); bytes += original?.bytes.length ?? 0;
        require(!original || Buffer.from(original.bytes.toString('utf8')).equals(original.bytes), 'Only UTF-8 candidate targets are supported');
        return { path: f.path, content: original ? original.bytes.toString('utf8') : null, mode: original?.mode ?? 0o644 };
      });
      require(bytes <= CHANGE_LIMIT, 'Recovery material byte budget exceeded', 'E_RSI_CANDIDATE_BUDGET');
      require(input.files.some((f, i) => f.content !== originals[i].content), 'Candidate has no changes');
      const proposal = seal({ hypothesis: input.hypothesis, feedback: snap.feedback, files: input.files.map(f => ({ path: f.path, content: f.content })), originals, fingerprint: snap.fingerprint });
      if (policy) {
        require(snap.planSha256 === policy.planSha256, 'Approved RSI plan bytes changed', 'E_RSI_POLICY');
        const git = await gitIdentity(signal, previous?.automatic.anchorHead, read.io);
        if (previous) require(snap.frozenDigest === previous.automatic.frozenDigest && snap.targetDigest === previous.automatic.targetDigest, 'Automatic round inputs changed', 'E_RSI_STALE');
        const { automatic: oldAutomatic, ...oldState } = previous ?? {};
        automatic = { policyDigest, frozenDigest: snap.frozenDigest, targetDigest: snap.targetDigest, branch: git.branch, head: git.head, anchorHead: git.anchorHead, round: (oldAutomatic?.round ?? 0) + 1, maxRounds: policy.maxRounds, consecutiveFailures: oldAutomatic?.consecutiveFailures ?? 0, failuresAtStart: oldAutomatic?.consecutiveFailures ?? 0, history: oldAutomatic ? [...oldAutomatic.history, seal({ round: oldAutomatic.round, state: oldState })] : [] };
      }
      const s = { version: 1, status: 'proposed', proposal, evaluations: [], ...(automatic ? { automatic } : {}) };
      abort(signal); await save(s); return summary(s, read.io);
    });
  }
  async function evaluate({ signal } = {}) {
    return locked(async () => {
      const read = reader(base, signal), s = await load(read);
      require(s && ['proposed', 'evaluated'].includes(s.status), 'Evaluation requires a settled proposal; reconcile interrupted work first');
      const snap = await assertSource(read, s, signal);
      if (s.automatic || policy) { require(s.automatic && s.status === 'proposed', 'Automatic evaluation runs once per proposed round', 'E_RSI_RECONCILE'); await autoContext(s, reader(base, signal, read.io), signal); }
      require(s.evaluations.length < snap.plan.maxEvaluations, 'RSI evaluation count exhausted', 'E_RSI_EVALUATION_BUDGET');
      const record = { id: randomUUID(), proposalDigest: s.proposal.digest, complete: false, eligible: false, runs: [], runtime: snap.runtime };
      s.evaluations.push(seal(record)); s.status = 'evaluating'; abort(signal); await save(s);
      const workspace = await mkdtemp(join(tmpdir(), 'sage-rsi-'));
      try {
        for (const kind of ['baseline', 'candidate']) {
          abort(signal);
          const directory = join(workspace, kind); await mkdir(directory);
          for (const name of snap.plan.inputs) {
            const value = snap.files.get(name); if (!value) continue;
            await atomic(await safe(directory, name, signal), value.bytes, value.mode, signal);
          }
          if (kind === 'candidate') {
            for (const [i, f] of s.proposal.files.entries()) {
              const path = await safe(directory, f.path, signal);
              if (f.content === null) await unlink(path).catch(cause => { if (cause.code !== 'ENOENT') throw cause; });
              else await atomic(path, Buffer.from(f.content), s.proposal.originals[i].mode, signal);
            }
          }
          const before = await scan(directory, signal, read.io);
          const run = await runFixed(snap.plan.command, { cwd: directory, timeoutMs: snap.plan.timeoutMs, maxOutputBytes: snap.plan.maxOutputBytes, signal });
          let protection = false, ioAfter, protectionError;
          try { const after = await scan(directory, signal, read.io); protection = same(before.manifest, after.manifest); ioAfter = after.io; }
          catch (cause) { protectionError = cause.code ?? cause.name; }
          record.runs.push({ kind, ...run, protection, ...(protectionError ? { protectionError } : {}), ioBefore: before.io, ...(ioAfter ? { ioAfter } : {}) });
          // Failed protection/invalid baseline is diagnostic, never a comparable baseline.
          if (!goodRun(record.runs.at(-1))) break;
        }
        const finalRead = reader(base, signal, read.io); await assertSource(finalRead, s, signal);
        record.complete = true; record.eligible = eligible(record);
        if (policy) record.improvement = improvement(record, policy.improvement);
      } catch (cause) {
        record.complete = true; record.eligible = false; record.error = cause.code ?? cause.name;
        if (s.automatic && signal?.aborted) s.automatic.stopReason = 'interrupted';
      } finally {
        await rm(workspace, { recursive: true, force: true });
        s.evaluations[s.evaluations.length - 1] = seal(record); s.status = 'evaluated'; await save(s);
      }
      if (s.automatic) {
        abort(signal);
        if (record.eligible && record.improvement?.passed) return automaticAdopt(s, read.io, signal);
        failRound(s, record.error ?? 'no_improvement'); await save(s);
      }
      return summary(s, read.io);
    });
  }
  async function targets(read, s) {
    const actual = [];
    for (const [i, f] of s.proposal.files.entries()) {
      const original = s.proposal.originals[i], now = identity(await read.file(f.path, CHANGE_LIMIT, true));
      const before = original.content === null ? null : { sha256: hash(Buffer.from(original.content)), mode: original.mode };
      const after = f.content === null ? null : { sha256: hash(Buffer.from(f.content)), mode: original.mode };
      require(same(now, before) || same(now, after), 'Target has third-party changes; explicit reconciliation required', 'E_RSI_CONFLICT');
      actual.push(now);
    }
    return actual;
  }
  async function prepare(action, signal, budget) {
    const read = reader(base, signal, budget), s = await load(read);
    require(s, 'No RSI candidate');
    require(!s.automatic, 'Automatic round requires its bound project policy', 'E_RSI_POLICY');
    let authorityExpiresAt;
    if (action === 'adopt') {
      require(s.status === 'evaluated' && eligible(currentRecord(s)), 'Adoption requires eligible evaluation', 'E_RSI_NOT_ELIGIBLE');
      authorityExpiresAt = (await assertSource(read, s, signal)).plan.expiresAt;
    } else require(['applying', 'adopted', 'rolling_back'].includes(s.status), 'No adoption to roll back');
    const hostProtected = await protections(s.proposal.files.map(f => f.path), signal);
    const actual = await targets(read, s);
    const challenge = { action, proposalDigest: s.proposal.digest, evaluationDigest: currentRecord(s).digest, stateDigest: digest(s), actual, hostProtected, ...(authorityExpiresAt ? { authorityExpiresAt } : {}), changes: s.proposal.files.map((f, i) => ({ path: f.path, before: s.proposal.originals[i].content, after: f.content })), evaluation: currentRecord(s), expiresAt: new Date(Date.now() + 180000).toISOString() };
    return { s, read, challenge };
  }
  async function change(action, { authorize, signal } = {}) {
    require(!policy || action !== 'adopt', 'Automatic policy adopts only through evaluate', 'E_RSI_AUTOMATIC');
    if (policy && action === 'rollback') return locked(async () => { const read = reader(base, signal), s = await load(read); require(s?.status === 'adopted' && s.automatic, 'Automatic rollback requires a settled adopted round', 'E_RSI_RECONCILE'); await automaticRollback(s, read.io, signal, 'explicit_policy_rollback'); return summary(s, read.io); });
    const initial = await prepare(action, signal);
    require(typeof authorize === 'function', 'Explicit host human approval is required', 'E_RSI_APPROVAL');
    const supplied = structuredClone(initial.challenge);
    const approved = await authorize(supplied);
    abort(signal); require(approved === true, 'Human approval was not granted', 'E_RSI_APPROVAL');
    require(Date.now() < Date.parse(initial.challenge.expiresAt), 'Approval expired', 'E_RSI_APPROVAL');
    return locked(async () => {
      const fresh = await prepare(action, signal, initial.read.io);
      // Only expiry was generated per request; all relevant observations must match.
      fresh.challenge.expiresAt = initial.challenge.expiresAt;
      require(same(fresh.challenge, initial.challenge), 'Approval inputs changed while waiting', 'E_RSI_STALE');
      require(Date.now() < Date.parse(initial.challenge.expiresAt), 'Approval expired during revalidation', 'E_RSI_APPROVAL');
      require(!fresh.challenge.authorityExpiresAt || Date.now() < Date.parse(fresh.challenge.authorityExpiresAt), 'RSI authorization expired during revalidation', 'E_RSI_AUTHORITY');
      const s = fresh.s;
      if (action === 'adopt') s.approval = seal({ proposalDigest: s.proposal.digest, evaluationDigest: currentRecord(s).digest, binding: digest(initial.challenge), decidedAt: new Date().toISOString(), source: 'host-human-approval' });
      else s.rollbackApproval = seal({ binding: digest(initial.challenge), decidedAt: new Date().toISOString(), source: 'host-human-approval' });
      s.status = action === 'adopt' ? 'applying' : 'rolling_back'; abort(signal); await save(s);
      for (const [i, f] of s.proposal.files.entries()) {
        abort(signal);
        const target = await safe(base, f.path, signal), original = s.proposal.originals[i];
        const content = action === 'adopt' ? f.content : original.content;
        if (content === null) await unlink(target).catch(cause => { if (cause.code !== 'ENOENT') throw cause; });
        else await atomic(target, Buffer.from(content), original.mode, signal);
      }
      s.status = action === 'adopt' ? 'adopted' : 'rolled_back'; await save(s);
      return summary(s, fresh.read.io);
    });
  }
  async function inspect({ signal } = {}) {
    const read = reader(base, signal), s = await load(read);
    if (s && ['proposed', 'evaluating', 'evaluated'].includes(s.status)) await assertSource(read, s, signal);
    const result = summary(s, read.io);
    if (s && ['applying', 'verifying', 'observing', 'adopted', 'rolling_back', 'rolled_back'].includes(s.status)) {
      const actual = await targets(read, s);
      const matches = which => actual.every((value, i) => {
        const original = s.proposal.originals[i];
        const content = which === 'original' ? original.content : s.proposal.files[i].content;
        return same(value, content === null ? null : { sha256: hash(Buffer.from(content)), mode: original.mode });
      });
      result.targetState = matches('candidate') ? 'candidate' : matches('original') ? 'original' : 'mixed';
      if ((s.status === 'adopted' && result.targetState !== 'candidate') || (s.status === 'rolled_back' && result.targetState !== 'original')) result.next = 'reconcile';
    }
    return result;
  }
  async function recover({ signal } = {}) {
    return locked(async () => {
      const read = reader(base, signal), s = await load(read);
      require(s?.status === 'evaluating', 'Only interrupted evaluation can be settled here; adoption recovery requires approved rollback');
      const e = withoutDigest(currentRecord(s));
      e.complete = true; e.eligible = false; e.error = 'E_RSI_INTERRUPTED';
      s.evaluations[s.evaluations.length - 1] = seal(e); s.status = 'evaluated';
      if (s.automatic) { s.automatic.stopReason = 'interrupted'; }
      abort(signal); await save(s);
      return summary(s, read.io);
    });
  }
  return { propose, inspect, evaluate, observe, adopt: options => change('adopt', options), rollback: options => change('rollback', options), recover };
}
