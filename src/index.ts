/**
 * Stable, host-neutral library surface for SAGE-Kit integrations.
 *
 * The CLI remains the primary product surface; this entry exists so a host
 * adapter (for example the DSH plugin) can use the same file-mode state and
 * task/brief semantics without shelling out or reimplementing them.
 */
export {
  TASK_STATUSES,
  createTask,
  findActiveTask,
  isTaskStatus,
  listTasks,
  readTask,
  setTaskWorktree,
  updateTaskStatus,
} from "./core/tasks.js";
export type {
  CreateTaskInput,
  Task,
  TaskEvidence,
  TaskStatus,
  UpdateTaskOptions,
} from "./core/tasks.js";

export { buildBrief } from "./core/brief.js";
export type { BriefResult } from "./core/brief.js";

export {
  ensureStateDirs,
  findProjectRoot,
  homeDirectory,
  statePaths,
} from "./core/paths.js";
export type { StatePaths } from "./core/paths.js";

export { configExists, loadConfig } from "./core/config.js";
export type { SageConfig } from "./core/config.js";

export { SageError } from "./core/errors.js";
