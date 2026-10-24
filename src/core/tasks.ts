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
  createdAt: string;
  updatedAt: string;
}

const TRANSITIONS: Record<TaskStatus, readonly TaskStatus[]> = {
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

export function isTaskStatus(value: string): value is TaskStatus {
  return (TASK_STATUSES as readonly string[]).includes(value);
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  acceptance?: string[];
  id?: string;
  status?: TaskStatus;
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
  const now = nowIso();
  const task: Task = {
    schemaVersion: 1,
    id,
    title,
    description,
    status,
    acceptance,
    evidence: [],
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
  const newEvidence = (options.evidence ?? []).map((item) => ({
    at: nowIso(),
    note: cleanText(item, "evidence", 1000),
    ...(options.source ? { source: options.source.slice(0, 200) } : {}),
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
    { from, to: next, ...(options.note ? { note: cleanText(options.note, "note", 2000) } : {}) },
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
