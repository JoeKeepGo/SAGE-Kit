import { existsSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import type { TaskStatus } from "../core/tasks.js";
import { SageError } from "../core/errors.js";

// M2 control-plane foundation (DESIGN: docs/state-and-durability.md §2.2 and §6).
// The schema is the SQL projection of the §6 logical model. This module owns the
// per-project location, connection pragmas, migrations and row decoding helpers.

export const CONTROL_SCHEMA_VERSION = 1;
export const CONTROL_DIR_NAME = "control";
export const CONTROL_DB_NAME = "control.db";
export const DEFAULT_LEASE_TTL_MS = 30_000;
export const DEFAULT_HEARTBEAT_MS = 10_000;
export const DEFAULT_BUSY_TIMEOUT_MS = 5_000;
export const MAX_EVENT_PAYLOAD_BYTES = 32_768;
export const MAX_HTTP_BODY_BYTES = 65_536;

/**
 * Authoritative *status* transitions are `TASK_STATUSES` in `src/core/tasks.ts`;
 * that module keeps `TRANSITIONS` private, so the control store mirrors the same
 * table here. `tests/control.test.mjs` exercises the same edges as the P0 file
 * mode. Keep this in sync with `src/core/tasks.ts:42-52`.
 */
export const TASK_TRANSITIONS: Record<TaskStatus, readonly TaskStatus[]> = {
  imported: ["ready", "blocked", "failed"],
  ready: ["running", "blocked", "failed", "cancelled"],
  running: ["review", "blocked", "failed", "cancelled", "interrupted"],
  review: ["done", "running", "blocked", "failed", "cancelled"],
  done: [],
  blocked: ["ready", "running", "failed", "cancelled"],
  failed: ["ready", "running"],
  cancelled: [],
  interrupted: ["ready", "running", "failed"],
};

export interface ControlPaths {
  projectRoot: string;
  controlDir: string;
  dbPath: string;
  lockPath: string;
  walPath: string;
  shmPath: string;
}

export function controlPaths(projectRoot: string): ControlPaths {
  const root = resolve(projectRoot);
  const controlDir = join(root, ".sage-kit", CONTROL_DIR_NAME);
  const dbPath = join(controlDir, CONTROL_DB_NAME);
  return {
    projectRoot: root,
    controlDir,
    dbPath,
    lockPath: join(controlDir, "writer.lock"),
    walPath: `${dbPath}-wal`,
    shmPath: `${dbPath}-shm`,
  };
}

export function controlDbPath(projectRoot: string): string {
  return controlPaths(projectRoot).dbPath;
}

/** Create `.sage-kit/control/` (the only state directory this module writes). */
export function ensureControlPaths(projectRoot: string): ControlPaths {
  const paths = controlPaths(projectRoot);
  if (!existsSync(paths.controlDir)) mkdirSync(paths.controlDir, { recursive: true, mode: 0o700 });
  return paths;
}

export interface ControlEvidence {
  at: string;
  note: string;
  source?: string;
}

export interface ControlTask {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: number;
  acceptance: string[];
  evidence: ControlEvidence[];
  source?: string;
  externalId?: string;
  externalUrl?: string;
  worktreePath?: string;
  branch?: string;
  blockedReason?: string;
  idempotencyKey?: string;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface CreateTaskInput {
  id?: string;
  title: string;
  description?: string;
  status?: TaskStatus;
  priority?: number;
  acceptance?: string[];
  worktreePath?: string;
  branch?: string;
  source?: string;
  externalId?: string;
  externalUrl?: string;
  idempotencyKey?: string;
}

export interface UpdateTaskStatusOptions {
  evidence?: string[];
  note?: string;
  source?: string;
  blockedReason?: string;
  expectedVersion?: number;
  /** Deterministic clock override (ISO 8601) used by tests and recovery scans. */
  now?: string;
}

export const RUN_STATUSES = ["starting", "running", "exited", "failed", "cancelled", "interrupted"] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];
export const ACTIVE_RUN_STATUSES: readonly RunStatus[] = ["starting", "running"];
export const TERMINAL_RUN_STATUSES: readonly RunStatus[] = ["exited", "failed", "cancelled", "interrupted"];

export function isRunStatus(value: string): value is RunStatus {
  return (RUN_STATUSES as readonly string[]).includes(value);
}

export interface ControlRun {
  id: string;
  taskId: string;
  host: string;
  status: RunStatus;
  command?: string[];
  worktreePath?: string;
  exitCode?: number;
  costUsd?: number;
  inputTokens?: number;
  outputTokens?: number;
  errorCode?: string;
  errorMessage?: string;
  startedAt: string;
  endedAt?: string;
  idempotencyKey?: string;
}

export interface RecordRunInput {
  id?: string;
  taskId: string;
  host?: string;
  status?: "starting" | "running";
  command?: string[];
  worktreePath?: string;
  startedAt?: string;
  idempotencyKey?: string;
}

export interface FinishRunInput {
  status: Exclude<RunStatus, "starting" | "running">;
  exitCode?: number | null;
  costUsd?: number;
  inputTokens?: number;
  outputTokens?: number;
  errorCode?: string;
  errorMessage?: string;
  endedAt?: string;
}

export interface ControlEvent {
  id: string;
  seq: number;
  taskId?: string;
  runId?: string;
  type: string;
  data: unknown;
  createdAt: string;
}

export interface AppendEventInput {
  type: string;
  data?: unknown;
  taskId?: string;
  runId?: string;
  /** Deterministic clock override (ISO 8601) used by tests. */
  createdAt?: string;
}

export interface ListEventsOptions {
  taskId?: string;
  runId?: string;
  type?: string;
  limit?: number;
}

export interface ControlLease {
  taskId: string;
  owner: string;
  runId?: string;
  acquiredAt: string;
  heartbeatAt: string;
  expiresAt: string;
}

export interface AcquireLeaseOptions {
  owner: string;
  runId?: string;
  ttlMs?: number;
  /** Deterministic clock override (ISO 8601) used by tests. */
  now?: string;
}

export interface RenewLeaseOptions {
  owner: string;
  ttlMs?: number;
  now?: string;
}

export interface ReleaseLeaseOptions {
  owner?: string;
  now?: string;
}

export interface ExpireLeasesOptions {
  now?: string;
}

export interface RecoveryReport {
  scannedAt: string;
  expiredLeases: ControlLease[];
  interruptedRuns: ControlRun[];
  interruptedTasks: string[];
}

export interface ControlStoreOptions {
  dbPath?: string;
  readOnly?: boolean;
  leaseTtlMs?: number;
  heartbeatMs?: number;
  clock?: () => Date;
}

export interface ControlDebugInfo {
  projectRoot: string;
  dbPath: string;
  readOnly: boolean;
  journalMode: string;
  foreignKeys: number;
  busyTimeout: number;
  synchronous: number;
  userVersion: number;
  leaseTtlMs: number;
  heartbeatMs: number;
}

/**
 * v1 schema: minimal `tasks`/`runs`/`events`/`leases` from
 * docs/state-and-durability.md §6.1/§6.2.
 *
 * M2 extension: `tasks.evidence_json` is not in §6.1 but is required to reuse
 * the P0 invariant "done needs at least one evidence item" (§3.1). It is an
 * additive column, documented in docs/m2-control.md.
 */
const CONTROL_SCHEMA_V1 = `
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  acceptance_json TEXT NOT NULL DEFAULT '[]',
  evidence_json TEXT NOT NULL DEFAULT '[]',
  source TEXT,
  external_id TEXT,
  external_url TEXT,
  worktree_path TEXT,
  branch TEXT,
  blocked_reason TEXT,
  idempotency_key TEXT UNIQUE,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS tasks_updated ON tasks(updated_at);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  host TEXT NOT NULL,
  status TEXT NOT NULL,
  command TEXT,
  worktree_path TEXT,
  exit_code INTEGER,
  cost_usd REAL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  error_code TEXT,
  error_message TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  idempotency_key TEXT UNIQUE
) STRICT;

CREATE INDEX IF NOT EXISTS runs_task ON runs(task_id);
CREATE INDEX IF NOT EXISTS runs_status ON runs(status);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  seq INTEGER NOT NULL,
  task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
  run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS events_run_seq ON events(run_id, seq) WHERE run_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS events_task_seq ON events(task_id, seq) WHERE task_id IS NOT NULL AND run_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS events_global_seq ON events(seq) WHERE task_id IS NULL AND run_id IS NULL;
CREATE INDEX IF NOT EXISTS events_created ON events(created_at);

CREATE TABLE IF NOT EXISTS leases (
  task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
  owner TEXT NOT NULL,
  run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
  acquired_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS leases_expires ON leases(expires_at);
`;

export interface ConfigureDatabaseOptions {
  readOnly?: boolean;
}

/** Apply the §2.2 pragmas: busy_timeout, WAL, synchronous=FULL, foreign_keys=ON. */
export function configureDatabase(db: DatabaseSync, options: ConfigureDatabaseOptions = {}): void {
  db.exec(`PRAGMA busy_timeout = ${DEFAULT_BUSY_TIMEOUT_MS}`);
  if (!options.readOnly) {
    db.exec("PRAGMA journal_mode = WAL");
    db.exec("PRAGMA synchronous = FULL");
  }
  db.exec("PRAGMA foreign_keys = ON");
  const journalMode = String(readPragmaValue(db, "journal_mode")).toLowerCase();
  if (journalMode !== "wal") {
    throw new SageError(`Control database must use WAL journal mode (got ${journalMode})`, "E_DB_PRAGMA", 1);
  }
  if (!options.readOnly && Number(readPragmaValue(db, "synchronous")) !== 2) {
    throw new SageError("Control database must run with synchronous=FULL", "E_DB_PRAGMA", 1);
  }
}

export function migrateDatabase(db: DatabaseSync): number {
  const version = Number(readPragmaValue(db, "user_version"));
  if (version === CONTROL_SCHEMA_VERSION) return version;
  if (version > CONTROL_SCHEMA_VERSION) {
    throw new SageError(
      `Control database schema version ${version} is newer than this build (${CONTROL_SCHEMA_VERSION})`,
      "E_DB_SCHEMA_NEWER",
      1,
    );
  }
  if (version !== 0) {
    throw new SageError(`No control database migration path from version ${version}`, "E_DB_MIGRATION", 1);
  }
  db.exec("BEGIN IMMEDIATE");
  try {
    db.exec(CONTROL_SCHEMA_V1);
    db.exec(`PRAGMA user_version = ${CONTROL_SCHEMA_VERSION}`);
    db.exec("COMMIT");
  } catch (error) {
    try {
      db.exec("ROLLBACK");
    } catch {
      // The original failure is the one that matters.
    }
    throw error;
  }
  return CONTROL_SCHEMA_VERSION;
}

export interface OpenDatabaseOptions {
  readOnly?: boolean;
}

export function openDatabase(dbPath: string, options: OpenDatabaseOptions = {}): DatabaseSync {
  const readOnly = options.readOnly === true;
  if (readOnly && !existsSync(dbPath)) {
    throw new SageError(`Control database does not exist: ${dbPath}`, "E_CONTROL_DB_NOT_FOUND", 1);
  }
  let db: DatabaseSync;
  try {
    db = new DatabaseSync(dbPath, { readOnly, enableForeignKeyConstraints: true });
  } catch (error) {
    throw new SageError(
      `Cannot open control database ${dbPath}: ${(error as Error).message}`,
      "E_CONTROL_DB_OPEN",
      1,
    );
  }
  try {
    configureDatabase(db, { readOnly });
    if (readOnly) {
      // A read-only connection cannot migrate; it must be an existing current DB.
      if (Number(readPragmaValue(db, "user_version")) === 0) {
        throw new SageError(`Control database is not initialized: ${dbPath}`, "E_CONTROL_DB_NOT_INITIALIZED", 1);
      }
    }
    migrateDatabase(db);
  } catch (error) {
    db.close();
    throw error;
  }
  return db;
}

export type SqlRow = Record<string, unknown>;

export function readPragmaValue(db: DatabaseSync, name: "journal_mode" | "foreign_keys" | "busy_timeout" | "synchronous" | "user_version"): string | number {
  // `name` is a closed union, so string interpolation cannot inject SQL.
  const row = db.prepare(`PRAGMA ${name}`).get();
  if (!row) throw new SageError(`PRAGMA ${name} returned no row`, "E_DB_PRAGMA", 1);
  const value = Object.values(row)[0];
  if (typeof value === "string" || typeof value === "number") return value;
  throw new SageError(`PRAGMA ${name} returned an unexpected value`, "E_DB_PRAGMA", 1);
}

export interface DatabasePragmas {
  journalMode: string;
  foreignKeys: number;
  busyTimeout: number;
  synchronous: number;
  userVersion: number;
}

export function readDatabasePragmas(db: DatabaseSync): DatabasePragmas {
  return {
    journalMode: String(readPragmaValue(db, "journal_mode")).toLowerCase(),
    foreignKeys: Number(readPragmaValue(db, "foreign_keys")),
    busyTimeout: Number(readPragmaValue(db, "busy_timeout")),
    synchronous: Number(readPragmaValue(db, "synchronous")),
    userVersion: Number(readPragmaValue(db, "user_version")),
  };
}

// ---- row decoding helpers -------------------------------------------------
// node:sqlite returns `Record<string, SQLOutputValue>` rows; these helpers turn
// them into the camelCase API shapes and convert corrupt rows into SageErrors.

export function readString(row: SqlRow, key: string, where: string): string {
  const value = row[key];
  if (typeof value !== "string") throw new SageError(`Corrupt control row in ${where}: ${key} is not text`, "E_BAD_DB_ROW", 1);
  return value;
}

export function readOptionalString(row: SqlRow, key: string, where: string): string | undefined {
  const value = row[key];
  if (value === null || value === undefined) return undefined;
  if (typeof value !== "string") throw new SageError(`Corrupt control row in ${where}: ${key} is not text`, "E_BAD_DB_ROW", 1);
  return value;
}

export function readNumber(row: SqlRow, key: string, where: string): number {
  const value = row[key];
  if (typeof value === "number") return value;
  if (typeof value === "bigint") return Number(value);
  throw new SageError(`Corrupt control row in ${where}: ${key} is not a number`, "E_BAD_DB_ROW", 1);
}

export function readOptionalNumber(row: SqlRow, key: string, where: string): number | undefined {
  const value = row[key];
  if (value === null || value === undefined) return undefined;
  if (typeof value === "number") return value;
  if (typeof value === "bigint") return Number(value);
  throw new SageError(`Corrupt control row in ${where}: ${key} is not a number`, "E_BAD_DB_ROW", 1);
}

export function parseJsonText(value: string, where: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch (error) {
    throw new SageError(`Corrupt control row in ${where}: invalid JSON (${(error as Error).message})`, "E_BAD_DB_ROW", 1);
  }
}

export function parseStringArrayText(value: string, where: string): string[] {
  const parsed = parseJsonText(value, where);
  if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) {
    throw new SageError(`Corrupt control row in ${where}: expected a string array`, "E_BAD_DB_ROW", 1);
  }
  return parsed as string[];
}

export function tablesInDatabase(db: DatabaseSync): string[] {
  const rows = db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").all() as SqlRow[];
  return rows.map((row) => readString(row, "name", "sqlite_master"));
}
