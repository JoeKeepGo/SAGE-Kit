// Optional host support. No model calls, command runner, network or daemon.
import { open, lstat, realpath, mkdir, rename, unlink } from 'node:fs/promises';
import { resolve, dirname, isAbsolute } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

const hash = value => createHash('sha256').update(value).digest('hex');
const fail = message => { throw new Error(message); };
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const text = x => typeof x === 'string' && x.trim().length > 0 && x.length <= 4096;
const id = x => typeof x === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(x);
const strings = (xs, test = text) => Array.isArray(xs) && xs.length <= 100 && xs.every(test);
const unique = xs => new Set(xs).size === xs.length;
const relativePath = x => text(x) && !isAbsolute(x) && !x.includes('\\') &&
  !x.includes(':') && !x.includes('\0') && x.split('/').length <= 32 &&
  x.split('/').every(p => p && p !== '.' && p !== '..');
const MAX_READ_BYTES = 8 * 1024 * 1024;
const MAX_READ_FILES = 128;
const MAX_STATE_BYTES = 4 * 1024 * 1024;
const readBudgetError = () => Object.assign(new Error('Continuation read budget exceeded; narrow the admitted round before retrying'), { code: 'E_READ_BUDGET' });

function normalizeResult(result, step) {
  if (!object(result) || !['passed', 'failed', 'not_executed'].includes(result.outcome) ||
      !Array.isArray(result.checks) || result.checks.length > 100 ||
      result.checks.some(c => !object(c) || !id(c.id) || typeof c.passed !== 'boolean' || !relativePath(c.evidence)) ||
      !unique(result.checks.map(c => c.id)) || (result.review !== undefined && !relativePath(result.review)) ||
      Object.keys(result).some(k => !['outcome', 'checks', 'review'].includes(k))) fail('Invalid result');
  const normalized = { outcome: result.outcome,
    checks: result.checks.map(c => ({ id: c.id, passed: c.passed, evidence: c.evidence })).sort((a, b) => a.id.localeCompare(b.id)),
    ...(result.review === undefined ? {} : { review: result.review }) };
  if (step && normalized.outcome === 'passed' &&
      (step.checks.some(name => !normalized.checks.some(c => c.id === name && c.passed)) ||
       normalized.checks.some(c => !c.passed) || (step.requiresReview && !normalized.review))) fail('Required checks/review missing or failed');
  return normalized;
}
const evidencePaths = result => [...new Set([...result.checks.map(c => c.evidence), ...(result.review ? [result.review] : [])])].sort();

function validatePlan(p) {
  if (!object(p) || p.version !== 1 || !text(p.goal) ||
      !strings(p.authority, relativePath) || !p.authority.length || !unique(p.authority) ||
      !strings(p.constraints) || !Number.isInteger(p.maxAttempts) || p.maxAttempts < 1 || p.maxAttempts > 1000 ||
      typeof p.expiresAt !== 'string' || !Number.isFinite(Date.parse(p.expiresAt)) ||
      typeof p.revoked !== 'boolean' || !Array.isArray(p.steps) || !p.steps.length || p.steps.length > 100) {
    fail('Invalid continuation plan');
  }
  for (const s of p.steps) {
    if (!object(s) || !id(s.id) || !text(s.objective) || !strings(s.dependsOn, id) ||
        !unique(s.dependsOn) || !strings(s.scope, relativePath) || !s.scope.length ||
        !strings(s.checks, id) || !unique(s.checks) ||
        ['requiresReview', 'admitted', 'humanGate'].some(k => typeof s[k] !== 'boolean')) {
      fail('Invalid continuation step');
    }
  }
  const steps = new Map(p.steps.map(s => [s.id, s]));
  if (steps.size !== p.steps.length) fail('Duplicate step id');
  const visited = new Set(), visiting = new Set();
  function visit(key) {
    if (!steps.has(key)) fail('Unknown dependency');
    if (visiting.has(key)) fail('Dependency cycle');
    if (visited.has(key)) return;
    visiting.add(key);
    for (const dep of steps.get(key).dependsOn) visit(dep);
    visiting.delete(key); visited.add(key);
  }
  for (const key of steps.keys()) visit(key);
}

export async function openContinuation({ root, planPath, statePath }) {
  const base = await realpath(root);
  if (!relativePath(planPath) || !relativePath(statePath) || planPath === statePath) fail('Invalid project paths');

  async function safePath(name) {
    if (!relativePath(name)) fail('Invalid relative path');
    let current = base;
    for (const part of name.split('/')) {
      current = resolve(current, part);
      try {
        if ((await lstat(current)).isSymbolicLink()) fail('Symlink paths are not supported');
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
    }
    return current;
  }
  function reader() {
    // Cache only within one operation; every later admission rechecks actual content.
    const contents = new Map(), digests = new Map();
    const io = { filesRead: 0, bytesRead: 0 };
    async function bytes(name, limit = 1024 * 1024) {
      const cached = contents.get(name);
      if (cached) {
        if (cached.length > limit) fail('File exceeds size limit');
        return cached;
      }
      if (io.filesRead >= MAX_READ_FILES || io.bytesRead >= MAX_READ_BYTES) throw readBudgetError();
      const path = await safePath(name);
      const info = await lstat(path);
      if (!info.isFile() || info.size > limit) fail('Expected bounded regular file');
      if (info.size > MAX_READ_BYTES - io.bytesRead) throw readBudgetError();
      const handle = await open(path, 'r');
      try {
        const stat = await handle.stat();
        if (!stat.isFile() || stat.size > limit) fail('Expected bounded regular file');
        if (stat.size > MAX_READ_BYTES - io.bytesRead) throw readBudgetError();
        // One sentinel byte detects concurrent growth without unbounded readFile allocation.
        const buffer = Buffer.alloc(stat.size + 1);
        io.filesRead++;
        let length = 0;
        while (length < buffer.length) {
          if (io.bytesRead === MAX_READ_BYTES) {
            if (length !== stat.size || (await handle.stat()).size !== stat.size) throw readBudgetError();
            break;
          }
          const result = await handle.read(buffer, length, Math.min(buffer.length - length, MAX_READ_BYTES - io.bytesRead), null);
          if (result.bytesRead === 0) break;
          length += result.bytesRead;
          io.bytesRead += result.bytesRead;
          if (length > stat.size) fail('File grew during bounded read');
        }
        const value = buffer.subarray(0, length);
        contents.set(name, value);
        return value;
      } finally { await handle.close(); }
    }
    return { bytes, io, async digest(name) {
      if (!digests.has(name)) digests.set(name, { path: name, sha256: hash(await bytes(name)) });
      return digests.get(name);
    } };
  }
  async function snapshot(read) {
    const p = JSON.parse((await read.bytes(planPath, 65536)).toString('utf8'));
    validatePlan(p);
    if (p.authority.includes(statePath) || p.authority.includes(planPath)) fail('Authority must be separate from plan/state');
    const authority = [];
    for (const path of p.authority) authority.push(await read.digest(path));
    const fingerprint = hash(JSON.stringify({ plan: p, authority }));
    return { plan: p, authority, fingerprint };
  }
  function validateState(s, snap) {
    if (!object(s) || s.version !== 1 || !/^[a-f0-9]{64}$/.test(s.fingerprint) ||
        !Array.isArray(s.attempts) || s.attempts.length > 1000) fail('Invalid continuation state');
    const ids = new Set();
    let active = 0;
    for (const a of s.attempts) {
      if (!object(a) || !id(a.id) || !id(a.stepId) || ids.has(a.id) ||
          !['running', 'passed', 'failed', 'not_executed'].includes(a.outcome)) fail('Invalid attempt');
      ids.add(a.id);
      if (a.outcome === 'running') {
        active++;
        if (a.result !== undefined || a.evidence !== undefined || a.resultKey !== undefined) fail('Invalid running attempt');
      } else {
        const step = s.fingerprint === snap.fingerprint ? snap.plan.steps.find(t => t.id === a.stepId) : undefined;
        const normalized = normalizeResult(a.result, step);
        if (a.result.outcome !== a.outcome || !Array.isArray(a.evidence) ||
            a.resultKey !== hash(JSON.stringify(normalized)) ||
            JSON.stringify(a.evidence.map(e => e?.path).sort()) !== JSON.stringify(evidencePaths(normalized))) {
          fail('Invalid finished attempt evidence');
        }
      }
      if (a.evidence?.some(e => !object(e) || !relativePath(e.path) || !/^[a-f0-9]{64}$/.test(e.sha256))) {
        fail('Invalid evidence digest');
      }
      if (s.fingerprint === snap.fingerprint && !snap.plan.steps.some(t => t.id === a.stepId)) fail('Unknown recorded step');
    }
    if (active > 1) fail('Multiple unresolved attempts');
  }
  async function readState(snap, read) {
    let raw;
    try { raw = await read.bytes(statePath, MAX_STATE_BYTES); }
    catch (error) {
      if (error.code === 'ENOENT') return { version: 1, fingerprint: snap.fingerprint, attempts: [] };
      throw error;
    }
    const state = JSON.parse(raw.toString('utf8'));
    validateState(state, snap);
    return state;
  }
  async function decision(snap, state, read) {
    const p = snap.plan;
    const context = { goal: p.goal, constraints: p.constraints, authority: snap.authority,
      maxAttempts: p.maxAttempts, expiresAt: p.expiresAt };
    const reply = (action, step, attempt) => ({ action,
      context: { ...context, ...(step ? { step } : {}) },
      ...(step ? { step } : {}), ...(attempt ? { attempt } : {}) });
    if (p.revoked) return reply('revoked');
    if (Date.now() >= Date.parse(p.expiresAt)) return reply('expired');
    if (state.fingerprint !== snap.fingerprint) return reply('authority_changed');
    for (const a of state.attempts.filter(a => a.outcome === 'passed')) {
      for (const e of a.evidence) {
        try { if ((await read.digest(e.path)).sha256 !== e.sha256) return reply('evidence_changed'); }
        catch (error) {
          if (error.code === 'E_READ_BUDGET') throw error;
          return reply('evidence_changed');
        }
      }
    }
    const active = state.attempts.find(a => a.outcome === 'running');
    if (active) return reply('reconcile', p.steps.find(s => s.id === active.stepId), active);
    const passed = new Set(state.attempts.filter(a => a.outcome === 'passed').map(a => a.stepId));
    if (p.steps.every(s => passed.has(s.id))) return reply('complete_pending_acceptance');
    if (state.attempts.length >= p.maxAttempts) return reply('budget_exhausted');
    let gate, reassess;
    for (const s of p.steps) {
      if (passed.has(s.id) || !s.admitted || !s.dependsOn.every(dep => passed.has(dep))) continue;
      if (s.humanGate) { gate ??= s; continue; }
      if (state.attempts.filter(a => a.stepId === s.id && a.outcome === 'failed').length >= 2) {
        reassess ??= s; continue;
      }
      return reply('continue', s);
    }
    return gate ? reply('human_gate', gate) : reassess ? reply('reassess', reassess) : reply('blocked');
  }
  async function persist(state, file) {
    const content = JSON.stringify(state, null, 2) + '\n';
    if (Buffer.byteLength(content) > MAX_STATE_BYTES) {
      throw Object.assign(new Error('Continuation state budget exceeded; reconcile and archive this round before continuing'), { code: 'E_STATE_BUDGET' });
    }
    const temp = `${file}.${randomUUID()}.tmp`;
    try {
      const h = await open(temp, 'wx', 0o600);
      try { await h.writeFile(content); await h.sync(); }
      finally { await h.close(); }
      await rename(temp, file);
    } finally { await unlink(temp).catch(error => { if (error.code !== 'ENOENT') throw error; }); }
  }
  async function mutate(fn) {
    const file = await safePath(statePath);
    await mkdir(dirname(file), { recursive: true });
    await safePath(statePath);
    const lock = await open(file + '.lock', 'wx', 0o600).catch(error => {
      if (error.code === 'EEXIST') fail('State is locked; verify its owner before clearing a stale lock');
      throw error;
    });
    try {
      await lock.writeFile(JSON.stringify({ pid: process.pid }));
      const read = reader();
      const snap = await snapshot(read), state = await readState(snap, read);
      const before = JSON.stringify(state);
      const result = await fn(snap, state, read);
      if (JSON.stringify(state) !== before) await persist(state, file);
      return result;
    } finally { await lock.close(); await unlink(file + '.lock'); }
  }
  return {
    async inspect() {
      const read = reader();
      const snap = await snapshot(read);
      const result = await decision(snap, await readState(snap, read), read);
      return { ...result, io: { ...read.io } };
    },
    async begin(stepId, attemptId) {
      if (!id(attemptId)) fail('Invalid attempt id');
      return mutate(async (snap, state, read) => {
        const existing = state.attempts.find(a => a.id === attemptId);
        if (existing) {
          if (existing.stepId !== stepId) fail('Attempt id belongs to another step');
          return { replayed: true, attempt: existing, step: snap.plan.steps.find(s => s.id === stepId) };
        }
        const next = await decision(snap, state, read);
        if (next.action !== 'continue' || next.step.id !== stepId) fail(`Cannot begin: ${next.action}`);
        const attempt = { id: attemptId, stepId, outcome: 'running' };
        state.attempts.push(attempt);
        return { replayed: false, attempt, step: next.step };
      });
    },
    async finish(attemptId, result) {
      return mutate(async (snap, state, read) => {
        if (state.fingerprint !== snap.fingerprint) fail('Authority changed; reconcile before recording');
        const a = state.attempts.find(a => a.id === attemptId);
        if (!a) fail('Unknown attempt');
        const step = snap.plan.steps.find(s => s.id === a.stepId);
        const normalized = normalizeResult(result, step);
        const key = hash(JSON.stringify(normalized));
        if (a.outcome !== 'running') {
          if (a.resultKey !== key) fail('Conflicting final result');
          return a;
        }
        const paths = evidencePaths(normalized);
        if (paths.some(p => [statePath, planPath, statePath + '.lock'].includes(p))) fail('Evidence must be separate from coordination files');
        const evidence = [];
        for (const p of new Set(paths)) evidence.push(await read.digest(p));
        Object.assign(a, { outcome: normalized.outcome, result: normalized, resultKey: key, evidence });
        return a;
      });
    },
  };
}
