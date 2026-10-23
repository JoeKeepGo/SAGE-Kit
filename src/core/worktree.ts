import { join, resolve, sep } from "node:path";
import { appendEvent } from "./events.js";
import { SageError } from "./errors.js";
import { ensureDir } from "./fs-utils.js";
import { git } from "./process.js";
import { readTask, setTaskWorktree, type Task } from "./tasks.js";
import type { StatePaths } from "./paths.js";

export interface WorktreeInfo {
  path: string;
  branch: string;
  head: string;
}

function assertInsideWorktrees(paths: StatePaths, candidate: string): string {
  const root = resolve(paths.worktreesDir) + sep;
  const target = resolve(candidate);
  if (!target.startsWith(root)) {
    throw new SageError("Worktree path escapes .sage-kit/worktrees", "E_UNSAFE_PATH", 2);
  }
  return target;
}

export async function createWorktree(paths: StatePaths, taskId: string): Promise<Task> {
  const task = await readTask(paths, taskId);
  if (task.worktree) {
    throw new SageError(`Task ${taskId} already has worktree: ${task.worktree}`, "E_WORKTREE_EXISTS", 1);
  }
  const root = await git(paths.projectRoot, ["rev-parse", "--show-toplevel"]);
  if (root.code !== 0) {
    throw new SageError("Worktree requires a git repository", "E_NOT_GIT", 1);
  }
  const worktreePath = assertInsideWorktrees(paths, join(paths.worktreesDir, taskId));
  const branch = `sage-kit/${taskId}`;
  await ensureDir(paths.worktreesDir);
  let added = await git(paths.projectRoot, ["worktree", "add", "-b", branch, worktreePath, "HEAD"]);
  if (added.code !== 0 && /already exists/i.test(added.stderr)) {
    added = await git(paths.projectRoot, ["worktree", "add", worktreePath, branch]);
  }
  if (added.code !== 0) {
    throw new SageError(`git worktree add failed: ${added.stderr.trim()}`, "E_WORKTREE_FAILED", 1);
  }
  await appendEvent(paths, "worktree.created", { branch, path: worktreePath }, taskId);
  return setTaskWorktree(paths, taskId, { branch, worktree: worktreePath });
}

export async function removeWorktree(paths: StatePaths, taskId: string, force = false): Promise<Task> {
  const task = await readTask(paths, taskId);
  if (!task.worktree) throw new SageError(`Task ${taskId} has no worktree`, "E_NO_WORKTREE", 1);
  const worktreePath = assertInsideWorktrees(paths, task.worktree);
  if (!force) {
    const status = await git(worktreePath, ["status", "--porcelain"]);
    if (status.code === 0 && status.stdout.trim()) {
      throw new SageError(
        `Worktree is dirty; commit or use --force: ${worktreePath}`,
        "E_WORKTREE_DIRTY",
        1,
      );
    }
  }
  const removed = await git(paths.projectRoot, ["worktree", "remove", ...(force ? ["--force"] : []), worktreePath]);
  if (removed.code !== 0) {
    await git(paths.projectRoot, ["worktree", "prune"]);
    if (!force) {
      throw new SageError(`git worktree remove failed: ${removed.stderr.trim()}`, "E_WORKTREE_REMOVE_FAILED", 1);
    }
  }
  await appendEvent(paths, "worktree.removed", { path: worktreePath }, taskId);
  return setTaskWorktree(paths, taskId, null);
}

export async function listWorktrees(paths: StatePaths): Promise<WorktreeInfo[]> {
  const result = await git(paths.projectRoot, ["worktree", "list", "--porcelain"]);
  if (result.code !== 0) return [];
  const entries: WorktreeInfo[] = [];
  let current: Partial<WorktreeInfo> = {};
  for (const line of result.stdout.split(/\r?\n/)) {
    if (line.startsWith("worktree ")) {
      if (current.path) entries.push(current as WorktreeInfo);
      current = { path: line.slice("worktree ".length) };
    } else if (line.startsWith("branch ")) {
      current.branch = line.slice("branch ".length);
    } else if (line.startsWith("HEAD ")) {
      current.head = line.slice("HEAD ".length);
    }
  }
  if (current.path) entries.push(current as WorktreeInfo);
  return entries;
}
