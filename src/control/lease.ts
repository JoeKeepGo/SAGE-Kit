import type { DatabaseSync } from "node:sqlite";
import { validateTaskId } from "../core/fs-utils.js";
import { SageError } from "../core/errors.js";
import type { TaskStatus } from "../core/tasks.js";
import {
  ACTIVE_RUN_STATUSES,
  DEFAULT_HEARTBEAT_MS,
  DEFAULT_LEASE_TTL_MS,
  parseJsonText,
  readOptionalString,
  readString,
  type AcquireLeaseOptions,
  type AppendEventInput,
  type ControlEvent,
  type ControlLease,
  type ControlTask,
  type ExpireLeasesOptions,
  type ReleaseLeaseOptions,
  type RenewLeaseOptions,
  type RunStatus,
  type SqlRow,
  type UpdateTaskStatusOptions,
} from "./schema.js";

/**
 * The lease layer only depends on this narrow slice of `ControlStore`, so the
 * rules are testable independently and there is no runtime import cycle with
 * `store.ts` (which imports these functions for its instance methods).
 */
export interface LeaseStore {
  readonly db: DatabaseSync;
  readonly leaseTtlMs: number;
  readonly heartbeatMs: number;
  nowIso(): string;
  transaction<T>(fn: () => T): T;
  appendEvent(input: AppendEventInput): ControlEvent;
  getTask(id: string): ControlTask;
  updateTaskStatus(id: string, next: TaskStatus, options?: UpdateTaskStatusOptions): ControlTask;
}

export interface LeaseListOptions {
  includeExpired?: boolean;
  now?: string;
}

function requireOwner(owner: string): string {
  if (typeof owner !== "string") throw new SageError("Lease owner is required", "E_BAD_LEASE_OWNER", 2);
  const text = owner.trim();
  if (!text) throw new SageError("Lease owner must not be empty", "E_BAD_LEASE_OWNER", 2);
  if (text.length > 200) throw new SageError("Lease owner must be <= 200 characters", "E_BAD_LEASE_OWNER", 2);
  return text;
}

function normalizeTtl(ttlMs: number): number {
  if (!Number.isFinite(ttlMs) || ttlMs <= 0) {
    throw new SageError("Lease TTL must be a positive number of milliseconds", "E_BAD_LEASE_TTL", 2);
  }
  return Math.floor(ttlMs);
}

/** Normalize an explicit test clock (ISO 8601 string) against the store clock. */
export function resolveNowIso(now: string | undefined, fallback: string): string {
  if (now === undefined) return fallback;
  const parsed = Date.parse(now);
  if (!Number.isFinite(parsed)) throw new SageError(`Invalid timestamp: ${now}`, "E_BAD_TIME", 2);
  return new Date(parsed).toISOString();
}

export function leaseExpiry(nowIso: string, ttlMs: number): string {
  return new Date(Date.parse(nowIso) + ttlMs).toISOString();
}

function mapLease(row: SqlRow, where: string): ControlLease {
  const runId = readOptionalString(row, "run_id", where);
  return {
    taskId: readString(row, "task_id", where),
    owner: readString(row, "owner", where),
    ...(runId ? { runId } : {}),
    acquiredAt: readString(row, "acquired_at", where),
    heartbeatAt: readString(row, "heartbeat_at", where),
    expiresAt: readString(row, "expires_at", where),
  };
}

export function getLease(store: LeaseStore, taskId: string): ControlLease | undefined {
  const row = store.db.prepare("SELECT * FROM leases WHERE task_id = ?").get(taskId) as SqlRow | undefined;
  return row ? mapLease(row, "leases") : undefined;
}

export function listLeases(store: LeaseStore, options: LeaseListOptions = {}): ControlLease[] {
  const rows = store.db.prepare("SELECT * FROM leases ORDER BY task_id").all() as SqlRow[];
  const leases = rows.map((row) => mapLease(row, "leases"));
  if (options.includeExpired === false) {
    const now = resolveNowIso(options.now, store.nowIso());
    return leases.filter((lease) => lease.expiresAt > now);
  }
  return leases;
}

function requireRunForTask(store: LeaseStore, runId: string, taskId: string): void {
  const row = store.db.prepare("SELECT id, task_id FROM runs WHERE id = ?").get(runId) as SqlRow | undefined;
  if (!row) throw new SageError(`Run not found: ${runId}`, "E_RUN_NOT_FOUND", 1);
  const runTaskId = readString(row, "task_id", "runs");
  if (runTaskId !== taskId) {
    throw new SageError(`Run ${runId} does not belong to task ${taskId}`, "E_RUN_TASK_MISMATCH", 1);
  }
}

/**
 * Acquire the single lease for a task.
 *
 * - a valid lease held by anyone (including the same owner) is a conflict:
 *   `E_LEASE_HELD` (no double lease);
 * - an expired lease is swept first (task -> interrupted, associated run ->
 *   interrupted) and then the call fails with `E_LEASE_EXPIRED`: the control
 *   plane never silently re-runs or silently re-leases a crashed task. The
 *   caller must recover/confirm explicitly and retry.
 * - acquiring transitions the task to `running` using the state machine
 *   (`imported`/`done`/`cancelled` are rejected with `E_BAD_TRANSITION`).
 */
export function acquireLease(store: LeaseStore, taskId: string, options: AcquireLeaseOptions): ControlLease {
  const id = validateTaskId(taskId);
  const owner = requireOwner(options.owner);
  const ttlMs = normalizeTtl(options.ttlMs ?? store.leaseTtlMs);
  const now = resolveNowIso(options.now, store.nowIso());
  // Expiry side effects must commit even though the acquire itself is refused,
  // so the "expired" outcome is returned from the transaction and thrown after.
  const outcome = store.transaction(():
    | { kind: "acquired"; lease: ControlLease }
    | { kind: "held"; owner: string; expiresAt: string }
    | { kind: "expired"; expiresAt: string } => {
    store.getTask(id);
    if (options.runId !== undefined) requireRunForTask(store, options.runId, id);
    const existing = getLease(store, id);
    if (existing) {
      if (existing.expiresAt > now) return { kind: "held", owner: existing.owner, expiresAt: existing.expiresAt };
      expireOneLease(store, existing, now);
      return { kind: "expired", expiresAt: existing.expiresAt };
    }
    const task = store.getTask(id);
    if (task.status !== "running") {
      store.updateTaskStatus(id, "running", { note: `lease acquired by ${owner}`, now });
    }
    const lease: ControlLease = {
      taskId: id,
      owner,
      ...(options.runId !== undefined ? { runId: options.runId } : {}),
      acquiredAt: now,
      heartbeatAt: now,
      expiresAt: leaseExpiry(now, ttlMs),
    };
    store.db
      .prepare(
        "INSERT INTO leases (task_id, owner, run_id, acquired_at, heartbeat_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
      )
      .run(lease.taskId, lease.owner, lease.runId ?? null, lease.acquiredAt, lease.heartbeatAt, lease.expiresAt);
    store.appendEvent({
      type: "lease.acquired",
      taskId: id,
      data: { owner, runId: options.runId ?? null, expiresAt: lease.expiresAt, ttlMs },
      createdAt: now,
    });
    return { kind: "acquired", lease };
  });
  if (outcome.kind === "held") {
    throw new SageError(
      `Task ${id} is already leased by ${outcome.owner} until ${outcome.expiresAt}`,
      "E_LEASE_HELD",
      1,
    );
  }
  if (outcome.kind === "expired") {
    throw new SageError(
      `Lease for task ${id} expired at ${outcome.expiresAt}; task marked interrupted. Run recoverStale() and re-acquire explicitly.`,
      "E_LEASE_EXPIRED",
      1,
    );
  }
  return outcome.lease;
}

export function renewLease(store: LeaseStore, taskId: string, options: RenewLeaseOptions): ControlLease {
  const id = validateTaskId(taskId);
  const owner = requireOwner(options.owner);
  const ttlMs = normalizeTtl(options.ttlMs ?? store.leaseTtlMs);
  const now = resolveNowIso(options.now, store.nowIso());
  const outcome = store.transaction(():
    | { kind: "renewed"; lease: ControlLease }
    | { kind: "missing" }
    | { kind: "owner"; actual: string }
    | { kind: "expired"; expiresAt: string } => {
    const existing = getLease(store, id);
    if (!existing) return { kind: "missing" };
    if (existing.owner !== owner) return { kind: "owner", actual: existing.owner };
    if (existing.expiresAt <= now) {
      expireOneLease(store, existing, now);
      return { kind: "expired", expiresAt: existing.expiresAt };
    }
    const heartbeatAt = now;
    const expiresAt = leaseExpiry(now, ttlMs);
    store.db
      .prepare("UPDATE leases SET heartbeat_at = ?, expires_at = ? WHERE task_id = ?")
      .run(heartbeatAt, expiresAt, id);
    store.appendEvent({
      type: "lease.renewed",
      taskId: id,
      data: { owner, runId: existing.runId ?? null, heartbeatAt, expiresAt },
      createdAt: now,
    });
    return { kind: "renewed", lease: { ...existing, heartbeatAt, expiresAt } };
  });
  if (outcome.kind === "missing") throw new SageError(`Task ${id} has no lease to renew`, "E_LEASE_NOT_HELD", 1);
  if (outcome.kind === "owner") {
    throw new SageError(`Task ${id} lease is owned by ${outcome.actual}, not ${owner}`, "E_LEASE_OWNER_MISMATCH", 1);
  }
  if (outcome.kind === "expired") {
    throw new SageError(
      `Lease for task ${id} expired at ${outcome.expiresAt}; task marked interrupted. Run recoverStale() and re-acquire explicitly.`,
      "E_LEASE_EXPIRED",
      1,
    );
  }
  return outcome.lease;
}

export function releaseLease(store: LeaseStore, taskId: string, options: ReleaseLeaseOptions = {}): ControlLease {
  const id = validateTaskId(taskId);
  const now = resolveNowIso(options.now, store.nowIso());
  return store.transaction(() => {
    const existing = getLease(store, id);
    if (!existing) throw new SageError(`Task ${id} has no lease to release`, "E_LEASE_NOT_HELD", 1);
    if (options.owner !== undefined && requireOwner(options.owner) !== existing.owner) {
      throw new SageError(
        `Task ${id} lease is owned by ${existing.owner}, not ${options.owner}`,
        "E_LEASE_OWNER_MISMATCH",
        1,
      );
    }
    store.db.prepare("DELETE FROM leases WHERE task_id = ?").run(id);
    store.appendEvent({
      type: "lease.released",
      taskId: id,
      data: { owner: existing.owner, runId: existing.runId ?? null },
      createdAt: now,
    });
    return existing;
  });
}

/** Sweep every lease whose `expires_at <= now` and interrupt its task/run. */
export function expireLeases(store: LeaseStore, options: ExpireLeasesOptions = {}): ControlLease[] {
  const now = resolveNowIso(options.now, store.nowIso());
  return store.transaction(() => {
    const rows = store.db
      .prepare("SELECT * FROM leases WHERE expires_at <= ? ORDER BY expires_at, task_id")
      .all(now) as SqlRow[];
    const expired = rows.map((row) => mapLease(row, "leases"));
    for (const lease of expired) expireOneLease(store, lease, now);
    return expired;
  });
}

/**
 * Mark a single expired lease's task/run interrupted and delete the lease.
 * Never starts a new run or a new lease (recovery is not auto-rerun).
 */
function expireOneLease(store: LeaseStore, lease: ControlLease, now: string): void {
  let task: ControlTask | undefined;
  try {
    task = store.getTask(lease.taskId);
  } catch (error) {
    if (!(error instanceof SageError) || error.code !== "E_TASK_NOT_FOUND") throw error;
  }
  if (task && task.status === "running") {
    try {
      store.updateTaskStatus(task.id, "interrupted", { note: `lease owned by ${lease.owner} expired`, now });
    } catch (error) {
      // `done`/`cancelled` are terminal and simply stay as they are.
      if (!(error instanceof SageError) || error.code !== "E_BAD_TRANSITION") throw error;
    }
  }
  if (lease.runId) {
    const row = store.db.prepare("SELECT status, task_id FROM runs WHERE id = ?").get(lease.runId) as SqlRow | undefined;
    if (row) {
      const runStatus = readString(row, "status", "runs");
      if (ACTIVE_RUN_STATUSES.includes(runStatus as RunStatus)) {
        store.db
          .prepare("UPDATE runs SET status = 'interrupted', ended_at = ? WHERE id = ? AND status IN ('starting', 'running')")
          .run(now, lease.runId);
        store.appendEvent({
          type: "run.finished",
          taskId: lease.taskId,
          runId: lease.runId,
          data: { runId: lease.runId, status: "interrupted", reason: "lease_expired" },
          createdAt: now,
        });
      }
    }
  }
  store.db.prepare("DELETE FROM leases WHERE task_id = ?").run(lease.taskId);
  store.appendEvent({
    type: "lease.expired",
    taskId: lease.taskId,
    data: { owner: lease.owner, runId: lease.runId ?? null, expiredAt: now, expiresAt: lease.expiresAt },
    createdAt: now,
  });
}

export { DEFAULT_HEARTBEAT_MS, DEFAULT_LEASE_TTL_MS };

/** Exposed for recovery scans that need to decode a stored run payload. */
export function parseRunCommand(value: string | undefined): string[] | undefined {
  if (value === undefined) return undefined;
  const parsed = parseJsonText(value, "runs.command");
  if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) {
    throw new SageError("Corrupt control row in runs.command", "E_BAD_DB_ROW", 1);
  }
  return parsed as string[];
}
