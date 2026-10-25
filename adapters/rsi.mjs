// Optional, bounded RSI. Project authority selects inputs and commands; a host
// supplies human approval. Temporary directories are isolation, not a sandbox.
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
const goodRun = r => r && r.protection === true && Number.isInteger(r.exitCode) && r.exitCode >= 0 && r.timedOut === false && r.cancelled === false && r.outputExceeded === false;
const eligible = e => e?.complete === true && !e.error && e.runs?.length === 2 && e.runs[0].kind === 'baseline' && e.runs[1].kind === 'candidate' && e.runs.every(goodRun) && e.runs[1].exitCode === 0;

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

export async function openRSI({ root, planPath, statePath, protectedPaths = async () => [] }) {
  const base = await realpath(root);
  require(pathName(planPath) && pathName(statePath) && planPath !== statePath, 'Invalid RSI paths');
  const stateFile = await safe(base, statePath);
  require(typeof protectedPaths === 'function', 'Host protection resolver must be a function');
  async function protections(paths, signal) {
    const protectedList = await protectedPaths({ signal });
    require(Array.isArray(protectedList) && protectedList.length <= 128 && protectedList.every(pathName), 'Invalid host protection set');
    require(paths.every(path => !protectedList.includes(path)), 'RSI cannot change current host governance or control records', 'E_RSI_PROTECTED');
    return [...new Set(protectedList)].sort();
  }
  async function save(state) { await safe(base, statePath); await atomic(stateFile, Buffer.from(JSON.stringify(state, null, 2) + '\n')); }
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
    require(s.version === 1 && ['proposed', 'evaluating', 'evaluated', 'applying', 'adopted', 'rolling_back', 'rolled_back'].includes(s.status), 'Invalid RSI state');
    require(validSeal(s.proposal) && Array.isArray(s.evaluations) && s.evaluations.length <= 3, 'Invalid proposal/evaluation binding');
    validateCandidate(s.proposal);
    require(Array.isArray(s.proposal.originals) && s.proposal.originals.length === s.proposal.files.length && s.proposal.originals.every((f, i) => f.path === s.proposal.files[i].path && (f.content === null || typeof f.content === 'string') && Number.isInteger(f.mode)), 'Invalid recovery materials');
    require(Buffer.byteLength(JSON.stringify(s.proposal.originals)) <= CHANGE_LIMIT + 16384, 'Recovery materials exceed budget');
    for (const e of s.evaluations) {
      require(validSeal(e) && e.proposalDigest === s.proposal.digest && typeof e.complete === 'boolean', 'Invalid evaluation digest');
      require(e.eligible === eligible(e), 'Inconsistent evaluation verdict');
    }
    if (['applying', 'adopted', 'rolling_back', 'rolled_back'].includes(s.status)) {
      require(validSeal(s.approval) && s.approval.proposalDigest === s.proposal.digest && s.approval.evaluationDigest === currentRecord(s)?.digest && eligible(currentRecord(s)), 'Invalid adoption approval binding');
    }
    return s;
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
    return { plan: p, files, inputs, feedback, fingerprint, runtime };
  }
  function summary(s, io) {
    if (!s) return { status: 'empty', next: 'propose', io };
    const evaluation = currentRecord(s);
    return { status: s.status, next: s.status === 'proposed' ? 'evaluate' : s.status === 'evaluating' || ['applying', 'rolling_back'].includes(s.status) ? 'reconcile' : s.status === 'evaluated' ? (evaluation?.eligible ? 'human_approval' : 'review_failure') : s.status === 'adopted' ? 'observe_or_rollback' : 'complete', proposal: s.proposal, ...(evaluation ? { evaluation } : {}), ...(s.approval ? { approval: s.approval } : {}), io };
  }
  async function assertSource(read, s, signal) {
    const snap = await snapshot(read, s.proposal, signal);
    require(snap.fingerprint === s.proposal.fingerprint, 'RSI inputs changed; prepare and evaluate a new round', 'E_RSI_STALE');
    return snap;
  }
  async function propose(input, { signal } = {}) {
    validateCandidate(input);
    require(Object.keys(input).every(k => ['hypothesis', 'feedback', 'files'].includes(k)), 'Unexpected candidate field');
    return locked(async () => {
      const read = reader(base, signal);
      require(!(await load(read)), 'This RSI round already has a candidate');
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
      const s = { version: 1, status: 'proposed', proposal, evaluations: [] };
      abort(signal); await save(s); return summary(s, read.io);
    });
  }
  async function evaluate({ signal } = {}) {
    return locked(async () => {
      const read = reader(base, signal), s = await load(read);
      require(s && ['proposed', 'evaluated'].includes(s.status), 'Evaluation requires a settled proposal; reconcile interrupted work first');
      const snap = await assertSource(read, s, signal);
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
      } catch (cause) {
        record.complete = true; record.eligible = false; record.error = cause.code ?? cause.name;
      } finally {
        await rm(workspace, { recursive: true, force: true });
        s.evaluations[s.evaluations.length - 1] = seal(record); s.status = 'evaluated'; await save(s);
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
    if (s && ['applying', 'adopted', 'rolling_back', 'rolled_back'].includes(s.status)) {
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
      s.evaluations[s.evaluations.length - 1] = seal(e); s.status = 'evaluated'; abort(signal); await save(s);
      return summary(s, read.io);
    });
  }
  return { propose, inspect, evaluate, adopt: options => change('adopt', options), rollback: options => change('rollback', options), recover };
}
