/**
 * Real git worktree evaluation workspaces.
 *
 * The evaluator never runs the fixed suite in the source tree. Each baseline /
 * candidate run gets a throwaway `git worktree` checked out at the proposal's
 * base commit in the OS temp directory; the candidate is applied there, the
 * command runs there, and the worktree is removed afterwards (success, failure
 * or timeout). This keeps the main working tree, its index and uncommitted
 * changes completely untouched.
 *
 * Requirements / limits (docs/m3-rsi.md §2, §11):
 *   - the project root must be the repository root (RSI does not guess a
 *     subdirectory layout);
 *   - the proposal `baseCommit` must exist in the local repository
 *     (no fetch/network is performed);
 *   - stale worktree admin entries from a crash can be cleaned with
 *     `git worktree prune` (the evaluator also prunes on cleanup).
 *
 * GIT_TERMINAL_PROMPT=0 is inherited from `runFixedCommand`, and every git
 * invocation has a hard timeout.
 */
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { SageError } from "../core/errors.js";
import { exists } from "../core/fs-utils.js";
import { runFixedCommand } from "./process.js";

/** Wall-clock budget for one git plumbing command. */
export const DEFAULT_GIT_TIMEOUT_MS = 60_000;

export interface GitCommandResult {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
  /** Set when git could not be spawned at all (e.g. ENOENT). */
  spawnError?: string;
}

/** Run git without a shell, with captured output and a hard timeout. */
export async function runGitCommand(
  args: readonly string[],
  cwd: string,
  timeoutMs: number = DEFAULT_GIT_TIMEOUT_MS,
): Promise<GitCommandResult> {
  const result = await runFixedCommand(["git", ...args], cwd, { timeoutMs });
  const output: GitCommandResult = {
    exitCode: result.exitCode,
    stdout: result.stdout.trim(),
    stderr: result.stderr.trim(),
    timedOut: result.timedOut,
  };
  if (result.spawnError !== undefined) output.spawnError = result.spawnError;
  return output;
}

function gitFailure(operation: string, subject: string, result: GitCommandResult): SageError {
  const detail =
    result.spawnError ??
    (result.stderr ||
      result.stdout ||
      (result.timedOut ? `timed out after the git budget` : `exit code ${String(result.exitCode)}`));
  return new SageError(`${operation} failed for ${subject}: ${detail}`.slice(0, 2_000), "E_RSI_WORKTREE_FAILED", 1);
}

function samePath(left: string, right: string): boolean {
  const normalize = (value: string): string => {
    const resolved = resolve(value);
    return process.platform === "win32" ? resolved.toLowerCase() : resolved;
  };
  return normalize(left) === normalize(right);
}

/**
 * Ensure `projectRoot` is a git checkout and return its toplevel directory.
 * Throws `E_RSI_NOT_GIT_REPO` / `E_RSI_GIT_UNAVAILABLE` / `E_RSI_GIT_ROOT_MISMATCH`.
 */
export async function resolveGitRepository(projectRoot: string): Promise<string> {
  const result = await runGitCommand(["rev-parse", "--show-toplevel"], projectRoot);
  if (result.spawnError !== undefined) {
    throw new SageError(
      `git is required for RSI evaluation but could not be executed: ${result.spawnError}`,
      "E_RSI_GIT_UNAVAILABLE",
      1,
    );
  }
  if (result.exitCode !== 0 || !result.stdout) {
    throw new SageError(
      `RSI evaluation requires a git repository at ${resolve(projectRoot)} (${result.stderr || "not a git repository"})`,
      "E_RSI_NOT_GIT_REPO",
      1,
    );
  }
  const toplevel = result.stdout.trim();
  if (!samePath(toplevel, projectRoot)) {
    throw new SageError(
      `RSI evaluation requires the project root to be the git repository root: ${resolve(projectRoot)} != ${resolve(toplevel)}`,
      "E_RSI_GIT_ROOT_MISMATCH",
      1,
    );
  }
  return resolve(toplevel);
}

/**
 * Resolve a proposal `baseCommit` to a full commit id that exists locally.
 * Throws `E_RSI_BAD_BASE_COMMIT` when the commit is unknown or not a commit.
 */
export async function resolveBaseCommit(projectRoot: string, commit: string): Promise<string> {
  const result = await runGitCommand(["rev-parse", "--verify", "--quiet", `${commit}^{commit}`], projectRoot);
  if (result.exitCode !== 0 || !result.stdout) {
    throw new SageError(
      `baseCommit ${commit} is not available in the local repository; RSI does not fetch or invent commits`,
      "E_RSI_BAD_BASE_COMMIT",
      1,
    );
  }
  return result.stdout.trim();
}

export interface CreateWorktreeOptions {
  /** Git command timeout; defaults to `DEFAULT_GIT_TIMEOUT_MS`. */
  timeoutMs?: number;
}

/** A throwaway detached worktree plus its guaranteed cleanup. */
export interface GitWorktreeHandle {
  readonly kind: "git-worktree";
  readonly path: string;
  readonly repoRoot: string;
  /** Fully resolved commit id checked out by this worktree. */
  readonly commit: string;
  /**
   * Remove the worktree and its temporary parent. Returns true when both are
   * gone (including when they were already absent). Safe to call twice.
   */
  cleanup(): Promise<boolean>;
}

/**
 * Create a detached worktree for `commit` under a fresh OS temp directory.
 * Nothing is fetched; `commit` must already exist in `projectRoot`.
 */
export async function createEvaluationWorktree(
  projectRoot: string,
  commit: string,
  options: CreateWorktreeOptions = {},
): Promise<GitWorktreeHandle> {
  const repoRoot = await resolveGitRepository(projectRoot);
  const fullCommit = await resolveBaseCommit(repoRoot, commit);
  const timeoutMs = options.timeoutMs ?? DEFAULT_GIT_TIMEOUT_MS;

  let parent: string;
  try {
    parent = await mkdtemp(join(tmpdir(), "sage-kit-rsi-wt-"));
  } catch (error) {
    throw new SageError(
      `Cannot create RSI worktree parent: ${(error as Error).message}`,
      "E_RSI_WORKTREE_FAILED",
      1,
    );
  }
  const path = join(parent, "worktree");
  const add = await runGitCommand(["worktree", "add", "--detach", path, fullCommit], repoRoot, timeoutMs);
  if (add.exitCode !== 0) {
    await rm(parent, { recursive: true, force: true }).catch(() => undefined);
    throw gitFailure("git worktree add", fullCommit, add);
  }

  let removed = false;
  return {
    kind: "git-worktree",
    path,
    repoRoot,
    commit: fullCommit,
    cleanup: async (): Promise<boolean> => {
      if (removed) return true;
      try {
        const remove = await runGitCommand(["worktree", "remove", "--force", path], repoRoot, timeoutMs);
        if (remove.exitCode !== 0) {
          // Best effort fallback: drop the directory, then let git prune the
          // stale admin entry below.
          await rm(path, { recursive: true, force: true }).catch(() => undefined);
        }
        await runGitCommand(["worktree", "prune"], repoRoot, timeoutMs);
      } catch {
        await rm(path, { recursive: true, force: true }).catch(() => undefined);
      }
      await rm(parent, { recursive: true, force: true }).catch(() => undefined);
      removed = !(await exists(path)) && !(await exists(parent));
      return removed;
    },
  };
}
