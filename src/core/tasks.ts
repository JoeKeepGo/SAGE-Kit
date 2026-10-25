import { readdir } from "node:fs/promises";
import { exists, nowIso, randomToken, readJsonFile, validateTaskId, writeJsonAtomic } from "./fs-utils.js";
import { SageError } from "./errors.js";
import { appendEvent } from "./events.js";
import { taskFile } from "./paths.js";
import type { StatePaths } from "./paths.js";

export const TASK_STATUSES = [
  "imported",
  "ready",
  "running",
  "review",
  "done",
  "blocked",
  "failed",
  "cancelled",
  "interrupted",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export interface TaskEvidence {
  at: string;
  note: string;
  source?: string;
}

export interface Task {
  schemaVersion: 1;
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  acceptance: string[];
  evidence: TaskEvidence[];
  branch?: string;
  worktree?: string;
  /**
   * Optional link to the M3 RSI proposal that motivated this task. Only the
   * shape/id is validated here; whether the proposal is actually approved and
   * backed by a passed evaluation is checked by `checkRsiGate()` (read-only)
   * before a release/deploy action. Keeping the reference optional preserves
   * ordinary P0 task behavior and schemaVersion 1.
   */
  rsiProposalId?: string;
  createdAt: string;
  updatedAt: string;
}

const TRANSITIONS: Record<TaskStatus, readonly TaskStatus[]> = {
  imported: ["ready", "blocked", "failed"],
  ready: ["running", "blocked", "failed", "cancelled", "interrupted"],
  running: ["review", "blocked", "failed", "cancelled", "interrupted"],
  review: ["done", "running", "blocked", "failed", "cancelled", "interrupted"],
  done: [],
  blocked: ["ready", "running", "failed", "cancelled", "interrupted"],
  failed: ["ready", "running", "interrupted"],
  cancelled: [],
  interrupted: ["ready", "running", "failed"],
};

export function isTaskStatus(value: string): value is TaskStatus {
  return (TASK_STATUSES as readonly string[]).includes(value);
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  acceptance?: string[];
  id?: string;
  status?: TaskStatus;
  /** Optional M3 RSI proposal link; see `Task.rsiProposalId`. */
  rsiProposalId?: string;
}

/**
 * RSI proposal ids use the same shape as `src/rsi/validate.ts`
 * (`RSI_ID_PATTERN`). The pattern is duplicated here because core must not
 * import the optional RSI layer (core -> rsi would invert the dependency and
 * risk a cycle); both sides are pinned by tests.
 */
const RSI_PROPOSAL_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;

function cleanRsiProposalId(value: unknown): string {
  if (typeof value !== "string") {
    throw new SageError("rsiProposalId must be a string", "E_BAD_TASK", 2);
  }
  const text = value.trim();
  if (!RSI_PROPOSAL_ID_PATTERN.test(text)) {
    throw new SageError(
      `rsiProposalId must match ${RSI_PROPOSAL_ID_PATTERN} (RSI proposal id)`,
      "E_BAD_TASK",
      2,
    );
  }
  return text;
}

function cleanText(value: string, field: string, max: number): string {
  const text = value.trim();
  if (!text) throw new SageError(`${field} must not be empty`, "E_BAD_TASK", 2);
  if (text.length > max) throw new SageError(`${field} must be <= ${max} characters`, "E_BAD_TASK", 2);
  return text;
}

function taskIdFor(input?: string): string {
  if (input) return validateTaskId(input);
  const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
  return `task-${stamp}-${randomToken().slice(0, 6)}`;
}

export async function createTask(paths: StatePaths, input: CreateTaskInput): Promise<Task> {
  const title = cleanText(input.title, "title", 200);
  const description = input.description === undefined ? "" : cleanText(input.description, "description", 2000);
  const acceptance = (input.acceptance ?? []).map((item) => cleanText(item, "acceptance", 500)).slice(0, 20);
  const id = taskIdFor(input.id);
  if (await exists(taskFile(paths, id))) {
    throw new SageError(`Task already exists: ${id}`, "E_TASK_EXISTS", 1);
  }
  const status = input.status ?? "ready";
  if (!isTaskStatus(status)) throw new SageError(`Unknown status: ${status}`, "E_BAD_STATUS", 2);
  if (status === "done") throw new SageError("A new task cannot start as done", "E_BAD_STATUS", 2);
  const rsiProposalId =
    input.rsiProposalId === undefined ? undefined : cleanRsiProposalId(input.rsiProposalId);
  const now = nowIso();
  const task: Task = {
    schemaVersion: 1,
    id,
    title,
    description,
    status,
    acceptance,
    evidence: [],
    ...(rsiProposalId === undefined ? {} : { rsiProposalId }),
    createdAt: now,
    updatedAt: now,
  };
  await writeJsonAtomic(taskFile(paths, id), task);
  await appendEvent(paths, "task.created", { status, title }, id);
  return task;
}

export async function readTask(paths: StatePaths, id: string): Promise<Task> {
  validateTaskId(id);
  const path = taskFile(paths, id);
  if (!(await exists(path))) throw new SageError(`Task not found: ${id}`, "E_TASK_NOT_FOUND", 1);
  const task = await readJsonFile<Task>(path);
  if (task.schemaVersion !== 1 || task.id !== id || !isTaskStatus(task.status)) {
    throw new SageError(`Task file is invalid: ${id}`, "E_BAD_TASK_FILE", 1);
  }
  if (!Array.isArray(task.acceptance) || !Array.isArray(task.evidence)) {
    throw new SageError(`Task file is invalid: ${id}`, "E_BAD_TASK_FILE", 1);
  }
  if (
    task.rsiProposalId !== undefined &&
    (typeof task.rsiProposalId !== "string" || !RSI_PROPOSAL_ID_PATTERN.test(task.rsiProposalId))
  ) {
    throw new SageError(`Task file is invalid: ${id}`, "E_BAD_TASK_FILE", 1);
  }
  return task;
}

export async function listTasks(paths: StatePaths): Promise<Task[]> {
  let names: string[] = [];
  try {
    names = await readdir(paths.tasksDir);
  } catch {
    return [];
  }
  const tasks: Task[] = [];
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const id = name.slice(0, -5);
    try {
      validateTaskId(id);
      tasks.push(await readTask(paths, id));
    } catch {
      // A malformed task file must not make `task list` crash; doctor reports it.
    }
  }
  return tasks.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

/**
 * Strict task listing for enforcement paths (the DSH strict RSI gate).
 *
 * Unlike `listTasks()`, this never turns an unreadable directory, an invalid
 * task id, or a malformed task file into an empty list: absence of the task
 * directory is empty state, but any other read/validation failure throws so a
 * caller cannot silently lose an unapproved marker. Display paths should keep
 * using the tolerant `listTasks()`.
 */
export async function listTasksStrict(paths: StatePaths): Promise<Task[]> {
  let names: string[];
  try {
    names = await readdir(paths.tasksDir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw new SageError(
      `Cannot read task directory ${paths.tasksDir}: ${String(error)}`,
      "E_TASK_DIR_UNREADABLE",
      1,
    );
  }
  const tasks: Task[] = [];
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const id = name.slice(0, -5);
    validateTaskId(id);
    tasks.push(await readTask(paths, id));
  }
  return tasks.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export interface UpdateTaskOptions {
  evidence?: string[];
  note?: string;
  source?: string;
}

export async function updateTaskStatus(
  paths: StatePaths,
  id: string,
  next: TaskStatus,
  options: UpdateTaskOptions = {},
): Promise<Task> {
  const task = await readTask(paths, id);
  if (!TRANSITIONS[task.status].includes(next)) {
    throw new SageError(`Cannot move task ${id} from ${task.status} to ${next}`, "E_BAD_TRANSITION", 1);
  }
  // Validate every caller-supplied field before touching the task file. A
  // rejected note must not leave a committed status change behind.
  const note = options.note === undefined ? undefined : cleanText(options.note, "note", 2000);
  const source = options.source === undefined ? undefined : cleanText(options.source, "source", 200);
  const newEvidence = (options.evidence ?? []).map((item) => ({
    at: nowIso(),
    note: cleanText(item, "evidence", 1000),
    ...(source ? { source } : {}),
  }));
  const allEvidence = [...task.evidence, ...newEvidence];
  if (next === "done" && allEvidence.length === 0) {
    throw new SageError("Cannot mark done without at least one evidence item", "E_DONE_WITHOUT_EVIDENCE", 1);
  }
  const from = task.status;
  task.status = next;
  task.evidence = allEvidence;
  task.updatedAt = nowIso();
  await writeJsonAtomic(taskFile(paths, task.id), task);
  await appendEvent(
    paths,
    "task.status_changed",
    { from, to: next, ...(note === undefined ? {} : { note }) },
    task.id,
  );
  return task;
}

export async function setTaskWorktree(
  paths: StatePaths,
  id: string,
  worktree: { branch: string; worktree: string } | null,
): Promise<Task> {
  const task = await readTask(paths, id);
  if (worktree) {
    task.branch = worktree.branch;
    task.worktree = worktree.worktree;
  } else {
    delete task.branch;
    delete task.worktree;
  }
  task.updatedAt = nowIso();
  await writeJsonAtomic(taskFile(paths, task.id), task);
  await appendEvent(paths, worktree ? "task.worktree_attached" : "task.worktree_removed", {}, task.id);
  return task;
}

export function findActiveTask(tasks: Task[]): Task | undefined {
  const priority: TaskStatus[] = [
    "running",
    "review",
    "ready",
    "blocked",
    "imported",
    "interrupted",
    "failed",
    "done",
    "cancelled",
  ];
  for (const status of priority) {
    const found = tasks.find((task) => task.status === status);
    if (found) return found;
  }
  return undefined;
}
