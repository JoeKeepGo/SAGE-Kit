import { lstat, readFile, realpath } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { SageError } from "./errors.js";
import { exists, ensureDir, writeJsonAtomic } from "./fs-utils.js";

const PROJECT_REGISTRY = "sage-kit-project.json";

export interface StatePaths {
  projectRoot: string;
  stateDir: string;
  config: string;
  tasksDir: string;
  eventsDir: string;
  runsDir: string;
  worktreesDir: string;
  briefPath: string;
  cacheDir: string;
}

/** Parse the gitfile at `<root>/.git` and return its git dir, if any. */
async function gitDirFromGitfile(current: string): Promise<string | undefined> {
  try {
    const gitPath = join(current, ".git");
    const info = await lstat(gitPath);
    if (!info.isFile()) return undefined;
    const match = /^gitdir:\s*(.+)$/im.exec((await readFile(gitPath, "utf8")).trim());
    return match ? resolve(current, (match[1] as string).trim()) : undefined;
  } catch {
    return undefined;
  }
}

/** The shared git directory for a gitfile's git dir. */
async function commonGitDir(gitDir: string): Promise<string> {
  const commonFile = join(gitDir, "commondir");
  if (await exists(commonFile)) {
    return resolve(gitDir, (await readFile(commonFile, "utf8")).trim());
  }
  return gitDir;
}

/**
 * Persist the canonical project root inside the shared Git directory. A linked
 * worktree can read its common git dir but Git does not record the main
 * worktree path there for `--separate-git-dir` or submodule layouts, so this
 * registry is the only unambiguous bridge. Best-effort: a read-only git dir
 * must not make `init` fail.
 */
export async function writeProjectRegistry(projectRoot: string): Promise<void> {
  try {
    const gitDir = (await gitDirFromGitfile(projectRoot)) ?? join(projectRoot, ".git");
    const common = await commonGitDir(gitDir);
    if (!(await exists(common))) return;
    await writeJsonAtomic(join(common, PROJECT_REGISTRY), { projectRoot: resolve(projectRoot) });
  } catch {
    // Optional acceleration metadata; root resolution falls back to Git layout.
  }
}

async function sameCommonDir(a: string, b: string): Promise<boolean> {
  try {
    const [left, right] = await Promise.all([realpath(a), realpath(b)]);
    return process.platform === "win32" ? left.toLowerCase() === right.toLowerCase() : left === right;
  } catch {
    return false;
  }
}

async function readProjectRegistry(common: string): Promise<string | undefined> {
  try {
    const text = await readFile(join(common, PROJECT_REGISTRY), "utf8");
    const value = JSON.parse(text) as { projectRoot?: unknown };
    if (typeof value.projectRoot !== "string" || !isAbsolute(value.projectRoot)) return undefined;
    const candidate = resolve(value.projectRoot);
    if (!(await exists(join(candidate, ".sage-kit", "config.json")))) return undefined;
    // A moved/reused path can leave a stale registration that now names an
    // unrelated repository. Only accept it when both roots share the same Git
    // common directory, otherwise the linked worktree would read/write another
    // project's `.sage-kit` state.
    const candidateCommon = await commonDirForRoot(candidate);
    if (!candidateCommon || !(await sameCommonDir(common, candidateCommon))) return undefined;
    return candidate;
  } catch {
    return undefined;
  }
}

/** Common Git directory for a working tree, if it has one. */
async function commonDirForRoot(root: string): Promise<string | undefined> {
  try {
    const gitPath = join(root, ".git");
    const info = await lstat(gitPath);
    if (info.isDirectory()) return gitPath;
    if (!info.isFile()) return undefined;
    const gitDir = await gitDirFromGitfile(root);
    return gitDir ? commonGitDir(gitDir) : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Resolve a `.git` *file* to the project root that owns the `.sage-kit` state.
 *
 * A linked worktree's gitdir has a `commondir` file. When the common dir is
 * `main/.git`, its parent is the main worktree. For `--separate-git-dir` and
 * submodule layouts the common dir is elsewhere; the registry written by
 * `init` supplies the main path. Unknown layouts fail inward to the current
 * worktree instead of guessing a parent that may be Git metadata.
 */
async function gitProjectRoot(current: string): Promise<string> {
  try {
    const gitDir = await gitDirFromGitfile(current);
    if (!gitDir) return current;
    const common = await commonGitDir(gitDir);
    const registered = await readProjectRegistry(common);
    if (registered) return registered;
    if (basename(common).toLowerCase() === ".git") {
      // A normal linked worktree's common dir is the main worktree's `.git`.
      // A separate git dir can also be named `.git`; only treat the parent as
      // the main worktree when it actually owns this same common dir.
      const candidate = dirname(common);
      const candidateCommon = await commonDirForRoot(candidate);
      if (
        candidateCommon &&
        (await exists(join(candidate, ".sage-kit", "config.json"))) &&
        (await sameCommonDir(common, candidateCommon))
      ) {
        return candidate;
      }
    }
    const worktree = /^(.*)[/\\]\.git[/\\]worktrees[/\\][^/\\]+$/i.exec(gitDir);
    if (worktree && (await exists(join(worktree[1] as string, ".sage-kit", "config.json")))) {
      return worktree[1] as string;
    }
    return current;
  } catch {
    return current;
  }
}

export async function findProjectRoot(start: string, options: { strict?: boolean } = {}): Promise<string> {
  let current = resolve(start);
  for (;;) {
    // A nested initialized project wins over an enclosing git repository.
    if (await exists(join(current, ".sage-kit", "config.json"))) return current;
    if (await exists(join(current, ".git"))) {
      const root = await gitProjectRoot(current);
      if (root !== current) return root;
      // A linked worktree without a registry has no trustworthy main path.
      // Refuse to silently initialize a second state root there; the caller
      // must name the main worktree explicitly.
      const gitDir = await gitDirFromGitfile(current);
      if (options.strict && gitDir && /[/\\]worktrees[/\\][^/\\]+$/i.test(gitDir)) {
        throw new SageError(
          `Cannot determine the main worktree for linked worktree ${current} without a SAGE-Kit project registry; pass --project-root <main worktree>`,
          "E_PROJECT_ROOT_UNRESOLVED",
          1,
        );
      }
      return current;
    }
    const parent = dirname(current);
    if (parent === current) return resolve(start);
    current = parent;
  }
}

export function homeDirectory(env: NodeJS.ProcessEnv = process.env): string {
  return env.HOME || env.USERPROFILE || resolve(".");
}

export function packageRoot(importMetaUrl: string): string {
  return resolve(dirname(fileURLToPath(importMetaUrl)), "..", "..");
}

// For the CLI entry point (dist/cli.js or src/cli.ts) the package root is one
// level above the entry file's directory. Do not confuse it with packageRoot(),
// which is for modules nested one level below the package root (dist/core/*.js).
export function entryPackageRoot(importMetaUrl: string): string {
  return resolve(dirname(fileURLToPath(importMetaUrl)), "..");
}

export function skillSourceDir(root: string): string {
  return join(root, "skills", "sage-kit");
}

export function statePaths(projectRoot: string): StatePaths {
  const stateDir = join(projectRoot, ".sage-kit");
  return {
    projectRoot,
    stateDir,
    config: join(stateDir, "config.json"),
    tasksDir: join(stateDir, "state", "tasks"),
    eventsDir: join(stateDir, "state", "events"),
    runsDir: join(stateDir, "state", "runs"),
    worktreesDir: join(stateDir, "worktrees"),
    briefPath: join(projectRoot, "SESSION_BRIEF.md"),
    cacheDir: join(stateDir, "cache"),
  };
}

export async function ensureStateDirs(paths: StatePaths): Promise<void> {
  for (const dir of [paths.stateDir, paths.tasksDir, paths.eventsDir, paths.runsDir, paths.cacheDir]) {
    await ensureDir(dir);
  }
}

export function taskFile(paths: StatePaths, id: string): string {
  return join(paths.tasksDir, `${id}.json`);
}

export function eventsFile(paths: StatePaths): string {
  return join(paths.eventsDir, "events.jsonl");
}
