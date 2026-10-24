import { mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { hostname } from "node:os";
import type { DatabaseSync, SQLInputValue } from "node:sqlite";
import { SageError } from "../core/errors.js";
import { randomToken, redactRecord, validateTaskId } from "../core/fs-utils.js";
import { isTaskStatus, type TaskStatus } from "../core/tasks.js";
import {
  DEFAULT_HEARTBEAT_MS,
  DEFAULT_LEASE_TTL_MS,
  MAX_EVENT_PAYLOAD_BYTES,
  TERMINAL_RUN_STATUSES,
  TASK_TRANSITIONS,
  ensureControlPaths,
  isRunStatus,
  openDatabase,
  parseJsonText,
  parseStringArrayText,
  readDatabasePragmas,
  readNumber,
  readOptionalNumber,
  readOptionalString,
  readString,
  type AcquireLeaseOptions,
  type AppendEventInput,
  type ControlDebugInfo,
  type ControlEvent,
  type ControlEvidence,
  type ControlLease,
  type ControlPaths,
  type ControlRun,
  type ControlStoreOptions,
  type ControlTask,
  type CreateTaskInput,
  type ExpireLeasesOptions,
  type FinishRunInput,
  type ListEventsOptions,
  type RecordRunInput,
  type RecoveryReport,
  type ReleaseLeaseOptions,
  type RenewLeaseOptions,
  type RunStatus,
  type SqlRow,
  type UpdateTaskStatusOptions,
} from "./schema.js";
import {
  acquireLease as acquireLeaseImpl,
  expireLeases as expireLeasesImpl,
  getLease as getLeaseImpl,
  leaseExpiry,
  listLeases as listLeasesImpl,
  parseRunCommand,
  releaseLease as releaseLeaseImpl,
  renewLease as renewLeaseImpl,
  resolveNowIso,
  type LeaseListOptions,
} from "./lease.js";

const TASK_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;
const RUN_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;
const EVENT_TYPE_PATTERN = /^[a-z][a-z0-9._-]{0,99}$/;
const DEFAULT_LIST_LIMIT = 100;
const MAX_LIST_LIMIT = 1_000;

interface WriterLockInfo {
  pid: number;
  owner: string;
  startedAt: string;
}

function isProcessAlive(pid: number): boolean {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}

/**
 * Single-writer guard: the control plane allows only one writing process per
 * project. `ControlStore.close()` releases it; a lock whose owner pid is gone is
 * treated as stale and taken over. This is process-level, not a SQLite lock.
 */
function acquireWriterLock(lockPath: string, dbPath: string, owner: string): void {
  const info: WriterLockInfo = { pid: process.pid, owner, startedAt: new Date().toISOString() };
  const write = (): void => {
    writeFileSync(lockPath, `${JSON.stringify(info)}\n`, { encoding: "utf8", flag: "wx", mode: 0o600 });
  };
  try {
    write();
    return;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") {
      throw new SageError(`Cannot create control writer lock ${lockPath}: ${(error as Error).message}`, "E_WRITER_LOCK", 1);
    }
  }
  let existing: WriterLockInfo | undefined;
  try {
    const parsed: unknown = JSON.parse(readFileSync(lockPath, "utf8"));
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const record = parsed as Record<string, unknown>;
      if (
        typeof record.pid === "number" &&
        typeof record.owner === "string" &&
        typeof record.startedAt === "string" &&
        Number.isInteger(record.pid)
      ) {
        existing = { pid: record.pid, owner: record.owner, startedAt: record.startedAt };
      }
    }
  } catch {
    existing = undefined;
  }
  if (existing && isProcessAlive(existing.pid)) {
    throw new SageError(
      `Control database ${dbPath} is already open for writing by process ${existing.pid}; stop it before opening another control store`,
      "E_WRITER_LOCKED",
      1,
    );
  }
  // Stale lock from a crashed process (or corrupt lock content): take it over.
  try {
    unlinkSync(lockPath);
  } catch {
    // Another process may have removed it first; the retry below decides.
  }
  try {
    write();
  } catch (error) {
    throw new SageError(
      `Control database ${dbPath} is already open for writing: ${(error as Error).message}`,
      "E_WRITER_LOCKED",
      1,
    );
  }
}

function releaseWriterLock(lockPath: string, owner: string): void {
  try {
    const parsed: unknown = JSON.parse(readFileSync(lockPath, "utf8"));
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const record = parsed as Record<string, unknown>;
      if (record.owner === owner) unlinkSync(lockPath);
    }
  } catch {
    // Missing or unreadable lock means there is nothing to release.
  }
}

function cleanText(value: unknown, field: string, max: number, code = "E_BAD_TASK"): string {
  if (typeof value !== "string") throw new SageError(`${field} must be a string`, code, 2);
  const text = value.trim();
  if (!text) throw new SageError(`${field} must not be empty`, code, 2);
  if (text.length > max) throw new SageError(`${field} must be <= ${max} characters`, code, 2);
  return text;
}

function optionalText(value: unknown, field: string, max: number, code = "E_BAD_TASK"): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string") throw new SageError(`${field} must be a string`, code, 2);
  const text = value.trim();
  if (!text) return undefined;
  if (text.length > max) throw new SageError(`${field} must be <= ${max} characters`, code, 2);
  return text;
}

function nowStamp(iso: string): string {
  return iso.replace(/[-:T]/g, "").slice(0, 14);
}

function assertTaskStatus(value: string): TaskStatus {
  if (!isTaskStatus(value)) throw new SageError(`Unknown task status in database: ${value}`, "E_BAD_DB_ROW", 1);
  return value;
}

function assertRunStatus(value: string): RunStatus {
  if (!isRunStatus(value)) throw new SageError(`Unknown run status in database: ${value}`, "E_BAD_DB_ROW", 1);
  return value;
}

function validateRunId(id: string): string {
  if (typeof id !== "string" || !RUN_ID_PATTERN.test(id)) {
    throw new SageError("Run id must match [a-z0-9][a-z0-9-]{0,63}", "E_BAD_RUN_ID", 2);
  }
  return id;
}

function parseEvidence(value: string): ControlEvidence[] {
  const parsed = parseJsonText(value, "tasks.evidence_json");
  if (!Array.isArray(parsed)) throw new SageError("Corrupt control row in tasks.evidence_json", "E_BAD_DB_ROW", 1);
  const evidence: ControlEvidence[] = [];
  for (const item of parsed) {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new SageError("Corrupt control row in tasks.evidence_json", "E_BAD_DB_ROW", 1);
    }
    const record = item as Record<string, unknown>;
    if (typeof record.at !== "string" || typeof record.note !== "string") {
      throw new SageError("Corrupt control row in tasks.evidence_json", "E_BAD_DB_ROW", 1);
    }
    evidence.push({
      at: record.at,
      note: record.note,
      ...(typeof record.source === "string" ? { source: record.source } : {}),
    });
  }
  return evidence;
}

function mapTask(row: SqlRow): ControlTask {
  const where = "tasks";
  const task: ControlTask = {
    id: readString(row, "id", where),
    title: readString(row, "title", where),
    description: readString(row, "description", where),
    status: assertTaskStatus(readString(row, "status", where)),
    priority: readNumber(row, "priority", where),
    acceptance: parseStringArrayText(readString(row, "acceptance_json", where), "tasks.acceptance_json"),
    evidence: parseEvidence(readString(row, "evidence_json", where)),
    version: readNumber(row, "version", where),
    createdAt: readString(row, "created_at", where),
    updatedAt: readString(row, "updated_at", where),
  };
  const source = readOptionalString(row, "source", where);
  if (source !== undefined) task.source = source;
  const externalId = readOptionalString(row, "external_id", where);
  if (externalId !== undefined) task.externalId = externalId;
  const externalUrl = readOptionalString(row, "external_url", where);
  if (externalUrl !== undefined) task.externalUrl = externalUrl;
  const worktreePath = readOptionalString(row, "worktree_path", where);
  if (worktreePath !== undefined) task.worktreePath = worktreePath;
  const branch = readOptionalString(row, "branch", where);
  if (branch !== undefined) task.branch = branch;
  const blockedReason = readOptionalString(row, "blocked_reason", where);
  if (blockedReason !== undefined) task.blockedReason = blockedReason;
  const idempotencyKey = readOptionalString(row, "idempotency_key", where);
  if (idempotencyKey !== undefined) task.idempotencyKey = idempotencyKey;
  return task;
}

function mapRun(row: SqlRow): ControlRun {
  const where = "runs";
  const command = parseRunCommand(readOptionalString(row, "command", where) ?? undefined);
  const run: ControlRun = {
    id: readString(row, "id", where),
    taskId: readString(row, "task_id", where),
    host: readString(row, "host", where),
    status: assertRunStatus(readString(row, "status", where)),
    startedAt: readString(row, "started_at", where),
  };
  if (command !== undefined) run.command = command;
  const worktreePath = readOptionalString(row, "worktree_path", where);
  if (worktreePath !== undefined) run.worktreePath = worktreePath;
  const exitCode = readOptionalNumber(row, "exit_code", where);
  if (exitCode !== undefined) run.exitCode = exitCode;
  const costUsd = readOptionalNumber(row, "cost_usd", where);
  if (costUsd !== undefined) run.costUsd = costUsd;
  const inputTokens = readOptionalNumber(row, "input_tokens", where);
  if (inputTokens !== undefined) run.inputTokens = inputTokens;
  const outputTokens = readOptionalNumber(row, "output_tokens", where);
  if (outputTokens !== undefined) run.outputTokens = outputTokens;
  const errorCode = readOptionalString(row, "error_code", where);
  if (errorCode !== undefined) run.errorCode = errorCode;
  const errorMessage = readOptionalString(row, "error_message", where);
  if (errorMessage !== undefined) run.errorMessage = errorMessage;
  const endedAt = readOptionalString(row, "ended_at", where);
  if (endedAt !== undefined) run.endedAt = endedAt;
  const idempotencyKey = readOptionalString(row, "idempotency_key", where);
  if (idempotencyKey !== undefined) run.idempotencyKey = idempotencyKey;
  return run;
}

function mapEvent(row: SqlRow): ControlEvent {
  const where = "events";
  const event: ControlEvent = {
    id: readString(row, "id", where),
    seq: readNumber(row, "seq", where),
    type: readString(row, "type", where),
    data: parseJsonText(readString(row, "payload_json", where), "events.payload_json"),
    createdAt: readString(row, "created_at", where),
  };
  const taskId = readOptionalString(row, "task_id", where);
  if (taskId !== undefined) event.taskId = taskId;
  const runId = readOptionalString(row, "run_id", where);
  if (runId !== undefined) event.runId = runId;
  return event;
}

export interface ListTasksOptions {
  status?: TaskStatus;
  limit?: number;
}

export interface ListRunsOptions {
  taskId?: string;
  status?: RunStatus;
  limit?: number;
}

export interface RecoverStaleOptions {
  now?: string;
  /** Active runs older than this with no live lease are interrupted. Default 0. */
  staleRunAfterMs?: number;
}

/**
 * Optional M2 control-plane store: SQLite (WAL) single-writer state.
 *
 * This is additive, lazy-loadable state and never writes the P0 file-mode
 * `.sage-kit/state/` tree (D-005: one authoritative writer, no dual write).
 */
export class ControlStore {
  readonly projectRoot: string;
  readonly paths: ControlPaths;
  readonly db: DatabaseSync;
  readonly leaseTtlMs: number;
  readonly heartbeatMs: number;
  readonly readOnly: boolean;
  private readonly clock: () => Date;
  private readonly lockOwner?: string;
  private txDepth = 0;
  private closed = false;

  constructor(projectRoot: string, options: ControlStoreOptions = {}) {
    this.projectRoot = resolve(projectRoot);
    const basePaths = ensureControlPaths(this.projectRoot);
    if (options.dbPath !== undefined) {
      const dbPath = resolve(options.dbPath);
      if (dbPath !== basePaths.dbPath) mkdirSync(dirname(dbPath), { recursive: true });
      this.paths = { ...basePaths, dbPath, walPath: `${dbPath}-wal`, shmPath: `${dbPath}-shm` };
    } else {
      this.paths = basePaths;
    }
    this.readOnly = options.readOnly === true;
    this.clock = options.clock ?? ((): Date => new Date());
    this.leaseTtlMs = normalizePositiveInteger(options.leaseTtlMs ?? DEFAULT_LEASE_TTL_MS, "leaseTtlMs", "E_BAD_CONFIG");
    this.heartbeatMs = normalizePositiveInteger(options.heartbeatMs ?? DEFAULT_HEARTBEAT_MS, "heartbeatMs", "E_BAD_CONFIG");
    let owner: string | undefined;
    if (!this.readOnly) {
      owner = randomToken();
      acquireWriterLock(this.paths.lockPath, this.paths.dbPath, owner);
    }
    this.lockOwner = owner;
    try {
      this.db = openDatabase(this.paths.dbPath, { readOnly: this.readOnly });
    } catch (error) {
      if (owner !== undefined) releaseWriterLock(this.paths.lockPath, owner);
      throw error;
    }
  }

  /** Close the SQLite connection and release the single-writer lock. */
  close(): void {
    if (this.closed) return;
    this.closed = true;
    try {
      this.db.close();
    } finally {
      if (this.lockOwner !== undefined) releaseWriterLock(this.paths.lockPath, this.lockOwner);
    }
  }

  nowIso(): string {
    this.assertOpen();
    return this.clock().toISOString();
  }

  transaction<T>(fn: () => T): T {
    this.assertOpen();
    if (this.readOnly) throw new SageError("Control store is open read-only", "E_CONTROL_READ_ONLY", 1);
    if (this.txDepth > 0) return fn();
    this.db.exec("BEGIN IMMEDIATE");
    this.txDepth += 1;
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      try {
        this.db.exec("ROLLBACK");
      } catch {
        // The original failure is the one that matters.
      }
      throw error;
    } finally {
      this.txDepth -= 1;
    }
  }

  debugInfo(): ControlDebugInfo {
    this.assertOpen();
    const pragmas = readDatabasePragmas(this.db);
    return {
      projectRoot: this.projectRoot,
      dbPath: this.paths.dbPath,
      readOnly: this.readOnly,
      journalMode: pragmas.journalMode,
      foreignKeys: pragmas.foreignKeys,
      busyTimeout: pragmas.busyTimeout,
      synchronous: pragmas.synchronous,
      userVersion: pragmas.userVersion,
      leaseTtlMs: this.leaseTtlMs,
      heartbeatMs: this.heartbeatMs,
    };
  }

  // ---- tasks --------------------------------------------------------------

  createTask(input: CreateTaskInput): ControlTask {
    this.assertOpen();
    if (!input || typeof input !== "object") throw new SageError("Task input is required", "E_BAD_TASK", 2);
    const title = cleanText(input.title, "title", 200);
    const description = input.description === undefined ? "" : cleanText(input.description, "description", 2_000);
    const acceptance = (input.acceptance ?? [])
      .map((item) => cleanText(item, "acceptance", 500))
      .slice(0, 20);
    const status = input.status ?? "ready";
    if (!isTaskStatus(status)) throw new SageError(`Unknown status: ${status}`, "E_BAD_STATUS", 2);
    if (status === "done") throw new SageError("A new task cannot start as done", "E_BAD_STATUS", 2);
    const priority = input.priority ?? 0;
    if (!Number.isInteger(priority) || priority < -1_000_000 || priority > 1_000_000) {
      throw new SageError("priority must be an integer", "E_BAD_TASK", 2);
    }
    const id = input.id === undefined ? `task-${nowStamp(this.nowIso())}-${randomToken().slice(0, 6)}` : validateTaskId(input.id);
    const idempotencyKey = optionalText(input.idempotencyKey, "idempotencyKey", 200);
    const source = optionalText(input.source, "source", 200);
    const externalId = optionalText(input.externalId, "externalId", 200);
    const externalUrl = optionalText(input.externalUrl, "externalUrl", 2_000);
    const worktreePath = optionalText(input.worktreePath, "worktreePath", 2_000);
    const branch = optionalText(input.branch, "branch", 500);
    return this.transaction(() => {
      if (idempotencyKey !== undefined) {
        const existing = this.db.prepare("SELECT * FROM tasks WHERE idempotency_key = ?").get(idempotencyKey) as SqlRow | undefined;
        if (existing) return mapTask(existing);
      }
      if (this.db.prepare("SELECT 1 AS present FROM tasks WHERE id = ?").get(id)) {
        throw new SageError(`Task already exists: ${id}`, "E_TASK_EXISTS", 1);
      }
      const createdAt = this.nowIso();
      this.db
        .prepare(
          `INSERT INTO tasks (
             id, title, description, status, priority, acceptance_json, evidence_json,
             source, external_id, external_url, worktree_path, branch, idempotency_key, version, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          id,
          title,
          description,
          status,
          priority,
          JSON.stringify(acceptance),
          JSON.stringify([]),
          source ?? null,
          externalId ?? null,
          externalUrl ?? null,
          worktreePath ?? null,
          branch ?? null,
          idempotencyKey ?? null,
          1,
          createdAt,
          createdAt,
        );
      this.appendEvent({ type: "task.created", taskId: id, data: { status, title }, createdAt });
      return this.getTask(id);
    });
  }

  getTask(id: string): ControlTask {
    this.assertOpen();
    const taskId = validateTaskId(id);
    const row = this.db.prepare("SELECT * FROM tasks WHERE id = ?").get(taskId) as SqlRow | undefined;
    if (!row) throw new SageError(`Task not found: ${taskId}`, "E_TASK_NOT_FOUND", 1);
    return mapTask(row);
  }

  listTasks(options: ListTasksOptions = {}): ControlTask[] {
    this.assertOpen();
    const limit = normalizeLimit(options.limit);
    let sql = "SELECT * FROM tasks";
    const params: SQLInputValue[] = [];
    if (options.status !== undefined) {
      if (!isTaskStatus(options.status)) throw new SageError(`Unknown status: ${options.status}`, "E_BAD_STATUS", 2);
      sql += " WHERE status = ?";
      params.push(options.status);
    }
    sql += " ORDER BY updated_at DESC, id ASC LIMIT ?";
    params.push(limit);
    const rows = this.db.prepare(sql).all(...params) as SqlRow[];
    return rows.map(mapTask);
  }

  updateTaskStatus(id: string, next: TaskStatus, options: UpdateTaskStatusOptions = {}): ControlTask {
    this.assertOpen();
    const taskId = validateTaskId(id);
    if (!isTaskStatus(next)) throw new SageError(`Unknown status: ${next}`, "E_BAD_STATUS", 2);
    return this.transaction(() => {
      const task = this.getTask(taskId);
      if (options.expectedVersion !== undefined && task.version !== options.expectedVersion) {
        throw new SageError(
          `Task ${taskId} version conflict: expected ${options.expectedVersion}, found ${task.version}`,
          "E_TASK_VERSION_CONFLICT",
          1,
        );
      }
      if (!TASK_TRANSITIONS[task.status].includes(next)) {
        throw new SageError(`Cannot move task ${taskId} from ${task.status} to ${next}`, "E_BAD_TRANSITION", 1);
      }
      const now = options.now === undefined ? this.nowIso() : resolveNowIso(options.now, this.nowIso());
      const newEvidence = (options.evidence ?? []).map((item) => ({
        at: now,
        note: cleanText(item, "evidence", 1_000),
        ...(options.source ? { source: options.source.slice(0, 200) } : {}),
      }));
      const allEvidence = [...task.evidence, ...newEvidence];
      if (next === "done" && allEvidence.length === 0) {
        throw new SageError("Cannot mark done without at least one evidence item", "E_DONE_WITHOUT_EVIDENCE", 1);
      }
      const blockedReason = next === "blocked" ? (options.blockedReason ?? task.blockedReason ?? "blocked") : undefined;
      this.db
        .prepare(
          `UPDATE tasks SET status = ?, evidence_json = ?, blocked_reason = ?, version = version + 1, updated_at = ? WHERE id = ?`,
        )
        .run(next, JSON.stringify(allEvidence), blockedReason ?? null, now, taskId);
      this.appendEvent({
        type: "task.status_changed",
        taskId,
        data: { from: task.status, to: next, version: task.version + 1, ...(options.note ? { note: options.note } : {}) },
        createdAt: now,
      });
      return this.getTask(taskId);
    });
  }

  // ---- runs ---------------------------------------------------------------

  recordRun(input: RecordRunInput): ControlRun {
    this.assertOpen();
    if (!input || typeof input !== "object") throw new SageError("Run input is required", "E_BAD_RUN", 2);
    const taskId = validateTaskId(input.taskId);
    const status = input.status ?? "running";
    if (status !== "starting" && status !== "running") {
      throw new SageError(`A new run must start as starting or running (got ${String(status)})`, "E_BAD_RUN_STATUS", 2);
    }
    const host = optionalText(input.host, "host", 200) ?? hostname().slice(0, 200);
    const command = input.command === undefined ? undefined : this.normalizeCommand(input.command);
    const startedAt = input.startedAt === undefined ? this.nowIso() : resolveNowIso(input.startedAt, this.nowIso());
    const idempotencyKey = optionalText(input.idempotencyKey, "idempotencyKey", 200);
    const worktreePath = optionalText(input.worktreePath, "worktreePath", 2_000);
    return this.transaction(() => {
      this.getTask(taskId);
      if (idempotencyKey !== undefined) {
        const existing = this.db.prepare("SELECT * FROM runs WHERE idempotency_key = ?").get(idempotencyKey) as SqlRow | undefined;
        if (existing) return mapRun(existing);
      }
      const id = input.id === undefined ? `run-${nowStamp(startedAt)}-${randomToken().slice(0, 6)}` : validateRunId(input.id);
      if (this.db.prepare("SELECT 1 AS present FROM runs WHERE id = ?").get(id)) {
        throw new SageError(`Run already exists: ${id}`, "E_RUN_EXISTS", 1);
      }
      this.db
        .prepare(
          `INSERT INTO runs (
             id, task_id, host, status, command, worktree_path, started_at, idempotency_key
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          id,
          taskId,
          host,
          status,
          command === undefined ? null : JSON.stringify(command),
          worktreePath ?? null,
          startedAt,
          idempotencyKey ?? null,
        );
      this.appendEvent({
        type: "run.started",
        taskId,
        runId: id,
        data: { runId: id, host, status },
        createdAt: startedAt,
      });
      return this.getRun(id);
    });
  }

  getRun(id: string): ControlRun {
    this.assertOpen();
    const runId = validateRunId(id);
    const row = this.db.prepare("SELECT * FROM runs WHERE id = ?").get(runId) as SqlRow | undefined;
    if (!row) throw new SageError(`Run not found: ${runId}`, "E_RUN_NOT_FOUND", 1);
    return mapRun(row);
  }

  listRuns(options: ListRunsOptions = {}): ControlRun[] {
    this.assertOpen();
    const limit = normalizeLimit(options.limit);
    const where: string[] = [];
    const params: SQLInputValue[] = [];
    if (options.taskId !== undefined) {
      where.push("task_id = ?");
      params.push(validateTaskId(options.taskId));
    }
    if (options.status !== undefined) {
      if (!isRunStatus(options.status)) throw new SageError(`Unknown run status: ${options.status}`, "E_BAD_RUN_STATUS", 2);
      where.push("status = ?");
      params.push(options.status);
    }
    let sql = "SELECT * FROM runs";
    if (where.length > 0) sql += ` WHERE ${where.join(" AND ")}`;
    sql += " ORDER BY started_at DESC, id ASC LIMIT ?";
    params.push(limit);
    const rows = this.db.prepare(sql).all(...params) as SqlRow[];
    return rows.map(mapRun);
  }

  /**
   * Finish a run. Repeating the same terminal status is idempotent (returns the
   * stored row); changing an already-finished run is rejected.
   */
  finishRun(id: string, update: FinishRunInput): ControlRun {
    this.assertOpen();
    const runId = validateRunId(id);
    if (!update || typeof update !== "object") throw new SageError("Run update is required", "E_BAD_RUN", 2);
    if (!isRunStatus(update.status) || !TERMINAL_RUN_STATUSES.includes(update.status)) {
      throw new SageError(`Run status must be one of ${TERMINAL_RUN_STATUSES.join(", ")}`, "E_BAD_RUN_STATUS", 2);
    }
    return this.transaction(() => {
      const run = this.getRun(runId);
      if (TERMINAL_RUN_STATUSES.includes(run.status)) {
        if (run.status === update.status) return run;
        throw new SageError(
          `Run ${runId} is already finished as ${run.status}; cannot change to ${update.status}`,
          "E_RUN_ALREADY_FINISHED",
          1,
        );
      }
      const endedAt = update.endedAt === undefined ? this.nowIso() : resolveNowIso(update.endedAt, this.nowIso());
      const errorCode = optionalText(update.errorCode, "errorCode", 200);
      const errorMessage = optionalText(update.errorMessage, "errorMessage", 4_000);
      this.db
        .prepare(
          `UPDATE runs SET status = ?, exit_code = ?, cost_usd = ?, input_tokens = ?, output_tokens = ?,
             error_code = ?, error_message = ?, ended_at = ?
           WHERE id = ?`,
        )
        .run(
          update.status,
          update.exitCode ?? null,
          update.costUsd ?? null,
          update.inputTokens ?? null,
          update.outputTokens ?? null,
          errorCode ?? null,
          errorMessage ?? null,
          endedAt,
          runId,
        );
      this.appendEvent({
        type: "run.finished",
        taskId: run.taskId,
        runId,
        data: {
          runId,
          status: update.status,
          exitCode: update.exitCode ?? null,
          errorCode: errorCode ?? null,
        },
        createdAt: endedAt,
      });
      return this.getRun(runId);
    });
  }

  // ---- events -------------------------------------------------------------

  appendEvent(input: AppendEventInput): ControlEvent {
    this.assertOpen();
    if (!input || typeof input !== "object" || typeof input.type !== "string") {
      throw new SageError("Event type is required", "E_BAD_EVENT", 2);
    }
    const type = input.type.trim();
    if (!EVENT_TYPE_PATTERN.test(type)) {
      throw new SageError(`Event type must match ${EVENT_TYPE_PATTERN}`, "E_BAD_EVENT", 2);
    }
    let data: unknown;
    try {
      data = input.data === undefined ? {} : redactRecord(input.data);
    } catch (error) {
      throw new SageError(`Event payload cannot be serialized: ${(error as Error).message}`, "E_BAD_EVENT_DATA", 2);
    }
    let payloadJson: string;
    try {
      payloadJson = JSON.stringify(data);
    } catch (error) {
      throw new SageError(`Event payload cannot be serialized: ${(error as Error).message}`, "E_BAD_EVENT_DATA", 2);
    }
    if (payloadJson === undefined) payloadJson = "null";
    if (Buffer.byteLength(payloadJson, "utf8") > MAX_EVENT_PAYLOAD_BYTES) {
      throw new SageError(`Event payload exceeds ${MAX_EVENT_PAYLOAD_BYTES} bytes`, "E_EVENT_TOO_LARGE", 2);
    }
    let taskId: string | undefined;
    let runId: string | undefined;
    if (input.runId !== undefined) {
      runId = validateRunId(input.runId);
      const row = this.db.prepare("SELECT task_id FROM runs WHERE id = ?").get(runId) as SqlRow | undefined;
      if (!row) throw new SageError(`Run not found: ${runId}`, "E_RUN_NOT_FOUND", 1);
      const runTaskId = readString(row, "task_id", "runs");
      if (input.taskId !== undefined && input.taskId !== runTaskId) {
        throw new SageError(
          `Event scope mismatch: run ${runId} belongs to task ${runTaskId}, not ${input.taskId}`,
          "E_EVENT_SCOPE_MISMATCH",
          1,
        );
      }
      taskId = runTaskId;
    } else if (input.taskId !== undefined) {
      taskId = validateTaskId(input.taskId);
      this.getTask(taskId);
    }
    const createdAt = input.createdAt === undefined ? this.nowIso() : resolveNowIso(input.createdAt, this.nowIso());
    return this.transaction(() => {
      const seq = this.nextEventSeq(taskId, runId);
      const id = `evt-${nowStamp(createdAt)}-${randomToken().slice(0, 6)}`;
      this.db
        .prepare(
          "INSERT INTO events (id, seq, task_id, run_id, type, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        )
        .run(id, seq, taskId ?? null, runId ?? null, type, payloadJson, createdAt);
      return {
        id,
        seq,
        ...(taskId !== undefined ? { taskId } : {}),
        ...(runId !== undefined ? { runId } : {}),
        type,
        data,
        createdAt,
      };
    });
  }

  listEvents(options: ListEventsOptions = {}): ControlEvent[] {
    this.assertOpen();
    const limit = normalizeLimit(options.limit);
    const where: string[] = [];
    const params: SQLInputValue[] = [];
    if (options.taskId !== undefined) {
      where.push("task_id = ?");
      params.push(validateTaskId(options.taskId));
    }
    if (options.runId !== undefined) {
      where.push("run_id = ?");
      params.push(validateRunId(options.runId));
    }
    if (options.type !== undefined) {
      if (!EVENT_TYPE_PATTERN.test(options.type)) throw new SageError(`Event type must match ${EVENT_TYPE_PATTERN}`, "E_BAD_EVENT", 2);
      where.push("type = ?");
      params.push(options.type);
    }
    let sql = "SELECT * FROM events";
    if (where.length > 0) sql += ` WHERE ${where.join(" AND ")}`;
    sql += " ORDER BY created_at ASC, seq ASC LIMIT ?";
    params.push(limit);
    const rows = this.db.prepare(sql).all(...params) as SqlRow[];
    return rows.map(mapEvent);
  }

  // ---- leases (implemented in lease.ts; thin delegations keep one API) ----

  acquireLease(taskId: string, options: AcquireLeaseOptions): ControlLease {
    this.assertOpen();
    return acquireLeaseImpl(this, taskId, options);
  }

  renewLease(taskId: string, options: RenewLeaseOptions): ControlLease {
    this.assertOpen();
    return renewLeaseImpl(this, taskId, options);
  }

  releaseLease(taskId: string, options: ReleaseLeaseOptions = {}): ControlLease {
    this.assertOpen();
    return releaseLeaseImpl(this, taskId, options);
  }

  getLease(taskId: string): ControlLease | undefined {
    this.assertOpen();
    return getLeaseImpl(this, validateTaskId(taskId));
  }

  listLeases(options: LeaseListOptions = {}): ControlLease[] {
    this.assertOpen();
    return listLeasesImpl(this, options);
  }

  expireLeases(options: ExpireLeasesOptions = {}): ControlLease[] {
    this.assertOpen();
    return expireLeasesImpl(this, options);
  }

  // ---- recovery -----------------------------------------------------------

  /**
   * Recovery scan: sweep expired leases (task/run -> interrupted) and interrupt
   * active runs that have no live lease. Never starts a run or a new lease.
   *
   * `staleRunAfterMs` defaults to 0 so a control plane start (or explicit scan)
   * treats every active run without a live lease as orphaned. Provide a larger
   * window if an external runner records runs without leases.
   */
  recoverStale(options: RecoverStaleOptions = {}): RecoveryReport {
    this.assertOpen();
    const scannedAt = options.now === undefined ? this.nowIso() : resolveNowIso(options.now, this.nowIso());
    const staleRunAfterMs = options.staleRunAfterMs ?? 0;
    if (!Number.isFinite(staleRunAfterMs) || staleRunAfterMs < 0) {
      throw new SageError("staleRunAfterMs must be a non-negative number", "E_BAD_RECOVERY_OPTION", 2);
    }
    const expiredLeases = this.expireLeases({ now: scannedAt });
    const interruptedRuns: ControlRun[] = [];
    const interruptedTasks = new Set<string>();
    const cutoff = new Date(Date.parse(scannedAt) - staleRunAfterMs).toISOString();
    const activeRows = this.db
      .prepare("SELECT * FROM runs WHERE status IN ('starting', 'running') AND started_at <= ? ORDER BY started_at ASC, id ASC")
      .all(cutoff) as SqlRow[];
    for (const row of activeRows) {
      const run = mapRun(row);
      const lease = this.getLease(run.taskId);
      if (lease && lease.expiresAt > scannedAt) continue; // a live worker heartbeats this lease
      this.transaction(() => {
        this.db
          .prepare("UPDATE runs SET status = 'interrupted', ended_at = ? WHERE id = ? AND status IN ('starting', 'running')")
          .run(scannedAt, run.id);
        this.appendEvent({
          type: "run.finished",
          taskId: run.taskId,
          runId: run.id,
          data: { runId: run.id, status: "interrupted", reason: "stale_run" },
          createdAt: scannedAt,
        });
      });
      interruptedRuns.push({ ...run, status: "interrupted", endedAt: scannedAt });
      const remaining = this.db
        .prepare("SELECT COUNT(*) AS count FROM runs WHERE task_id = ? AND status IN ('starting', 'running')")
        .get(run.taskId) as SqlRow;
      if (readNumber(remaining, "count", "runs") !== 0) continue;
      try {
        const task = this.getTask(run.taskId);
        if (task.status === "running") {
          this.updateTaskStatus(task.id, "interrupted", { note: `stale run ${run.id}`, now: scannedAt });
          interruptedTasks.add(task.id);
        }
      } catch (error) {
        if (!(error instanceof SageError) || error.code !== "E_BAD_TRANSITION") throw error;
      }
    }
    if (expiredLeases.length > 0 || interruptedRuns.length > 0) {
      this.appendEvent({
        type: "control.recovered",
        data: {
          expiredLeases: expiredLeases.map((lease) => lease.taskId),
          interruptedRuns: interruptedRuns.map((run) => run.id),
          interruptedTasks: [...interruptedTasks],
        },
        createdAt: scannedAt,
      });
    }
    return { scannedAt, expiredLeases, interruptedRuns, interruptedTasks: [...interruptedTasks] };
  }

  // ---- internals ----------------------------------------------------------

  private assertOpen(): void {
    if (this.closed) throw new SageError("Control store is closed", "E_CONTROL_CLOSED", 1);
  }

  private nextEventSeq(taskId: string | undefined, runId: string | undefined): number {
    let row: SqlRow | undefined;
    if (runId !== undefined) {
      row = this.db.prepare("SELECT COALESCE(MAX(seq), 0) AS max_seq FROM events WHERE run_id = ?").get(runId) as
        | SqlRow
        | undefined;
    } else if (taskId !== undefined) {
      row = this.db
        .prepare("SELECT COALESCE(MAX(seq), 0) AS max_seq FROM events WHERE task_id = ? AND run_id IS NULL")
        .get(taskId) as SqlRow | undefined;
    } else {
      row = this.db
        .prepare("SELECT COALESCE(MAX(seq), 0) AS max_seq FROM events WHERE task_id IS NULL AND run_id IS NULL")
        .get() as SqlRow | undefined;
    }
    return readNumber(row ?? { max_seq: 0 }, "max_seq", "events") + 1;
  }

  private normalizeCommand(command: string[]): string[] {
    if (!Array.isArray(command) || command.some((item) => typeof item !== "string")) {
      throw new SageError("command must be an array of strings", "E_BAD_RUN_COMMAND", 2);
    }
    const cleaned = command.slice(0, 64).map((item) => item.slice(0, 500));
    const redacted = redactRecord(cleaned);
    if (!Array.isArray(redacted)) throw new SageError("command could not be redacted", "E_BAD_RUN_COMMAND", 2);
    return redacted.map((item) => String(item));
  }
}

function normalizePositiveInteger(value: number, field: string, code: string): number {
  if (!Number.isInteger(value) || value <= 0) throw new SageError(`${field} must be a positive integer`, code, 2);
  return value;
}

function normalizeLimit(limit: number | undefined): number {
  if (limit === undefined) return DEFAULT_LIST_LIMIT;
  if (!Number.isInteger(limit) || limit <= 0) {
    throw new SageError("limit must be a positive integer", "E_BAD_PAGINATION", 2);
  }
  return Math.min(limit, MAX_LIST_LIMIT);
}

/**
 * Open the optional control plane for a project. Creates `.sage-kit/control/`,
 * the SQLite database (WAL) and the single-writer lock. Synchronous because
 * `node:sqlite` is synchronous.
 */
export function openControl(projectRoot: string, options: ControlStoreOptions = {}): ControlStore {
  return new ControlStore(projectRoot, options);
}

/** Reference for the lease expiry calculation shared by acquire/renew. */
export { leaseExpiry };

/** Standalone form of `ControlStore.recoverStale()` for wiring code. */
export function recoverStale(store: ControlStore, options: RecoverStaleOptions = {}): RecoveryReport {
  return store.recoverStale(options);
}
