/**
 * Pure helpers shared by the DSH plugin. Kept free of DSH imports so they can
 * be unit-tested without installing the host runtime.
 */
import { existsSync, lstatSync, readFileSync, realpathSync } from "node:fs";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";

const PROJECT_REGISTRY = "sage-kit-project.json";

export const DEFAULT_BRIEF_BYTES = 2048;
export const MIN_BRIEF_BYTES = 256;
export const MAX_BRIEF_BYTES = 8192;
export const PLUGIN_MODES = ["off", "brief", "strict"];

/**
 * Resolve the plugin mode. `autoBrief:false` is kept for old profiles and is
 * only consulted when `mode` is absent; an explicit mode always wins.
 */
export function normalizeMode(value, autoBrief = true) {
  if (value === "off" || value === "brief" || value === "strict") return value;
  if (value === undefined || value === null || value === "") {
    return autoBrief === false ? "off" : "brief";
  }
  // Unknown values must not silently disable the brief; default to the safe
  // read-only mode and leave any enforcement to the explicit strict mode.
  return "brief";
}

/** Strict mode checks only tasks explicitly linked to an RSI proposal. */
export function isRsiGateRequired(mode, task) {
  return mode === "strict" && typeof task?.rsiProposalId === "string" && task.rsiProposalId.length > 0;
}

export function clampBriefBytes(value) {
  const n = Number.isFinite(value) ? Number(value) : DEFAULT_BRIEF_BYTES;
  return Math.min(MAX_BRIEF_BYTES, Math.max(MIN_BRIEF_BYTES, Math.trunc(n)));
}

/**
 * `projectRoot` is documented as an absolute path. A relative value is
 * ambiguous (DSH process cwd vs session cwd), so fail closed instead of
 * silently resolving it.
 */
export function configuredRoot(value, cwd = process.cwd()) {
  if (typeof value !== "string" || value.trim() === "") return undefined;
  if (!isAbsolute(value)) {
    throw new Error(`SAGE-Kit projectRoot must be an absolute path: ${value}`);
  }
  const root = resolve(cwd, value);
  if (!existsSync(join(root, ".sage-kit", "config.json"))) {
    throw new Error(`SAGE-Kit projectRoot is not initialized: ${root}`);
  }
  return root;
}

/**
 * Mirror the CLI's root semantics. A linked worktree (identified by the
 * `commondir` file in its gitdir) owns the main worktree's state; the project
 * registry written by `init` bridges separate-git-dir and submodule layouts
 * where Git does not record the main worktree path. A submodule or separate
 * git-dir without a registry is its own working tree.
 */
function commonGitDir(gitDir) {
  const commonFile = join(gitDir, "commondir");
  try {
    return resolve(gitDir, readFileSync(commonFile, "utf8").trim());
  } catch (error) {
    if (error.code === "ENOENT") return gitDir;
    throw error;
  }
}

function commonDirForRoot(root) {
  try {
    const gitPath = join(root, ".git");
    const info = lstatSync(gitPath);
    if (info.isDirectory()) return gitPath;
    if (!info.isFile()) return undefined;
    const match = /^gitdir:\s*(.+)$/im.exec(readFileSync(gitPath, "utf8").trim());
    if (!match) return undefined;
    return commonGitDir(resolve(root, match[1].trim()));
  } catch (error) {
    if (error.code === "ENOENT") return undefined;
    throw error;
  }
}

function samePath(a, b) {
  try {
    const left = realpathSync(a);
    const right = realpathSync(b);
    return process.platform === "win32" ? left.toLowerCase() === right.toLowerCase() : left === right;
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

function readProjectRegistry(common) {
  try {
    const value = JSON.parse(readFileSync(join(common, PROJECT_REGISTRY), "utf8"));
    if (typeof value.projectRoot !== "string" || !isAbsolute(value.projectRoot)) return undefined;
    const candidate = resolve(value.projectRoot);
    if (!existsSync(join(candidate, ".sage-kit", "config.json"))) return undefined;
    const candidateCommon = commonDirForRoot(candidate);
    if (!candidateCommon || !samePath(common, candidateCommon)) return undefined;
    return candidate;
  } catch (error) {
    if (error.code === "ENOENT") return undefined;
    throw error;
  }
}

function gitProjectRoot(current) {
  const gitPath = join(current, ".git");
  if (!lstatSync(gitPath).isFile()) return current;
  const match = /^gitdir:\s*(.+)$/im.exec(readFileSync(gitPath, "utf8").trim());
  if (!match) return current;
  const gitDir = resolve(current, match[1].trim());
  const common = commonGitDir(gitDir);
  const registered = readProjectRegistry(common);
  if (registered) return registered;
  if (basename(common).toLowerCase() === ".git") {
    // A normal linked worktree's common dir is the main worktree's `.git`.
    // A separate git dir can also be named `.git`; only accept its parent
    // when the parent owns the same common dir.
    const candidate = dirname(common);
    const candidateCommon = commonDirForRoot(candidate);
    if (
      candidateCommon &&
      existsSync(join(candidate, ".sage-kit", "config.json")) &&
      samePath(common, candidateCommon)
    ) {
      return candidate;
    }
  }
  const worktree = /^(.*)[/\\]\.git[/\\]worktrees[/\\][^/\\]+$/i.exec(gitDir);
  if (worktree && existsSync(join(worktree[1], ".sage-kit", "config.json"))) return worktree[1];
  return current;
}

/**
 * Mirror the CLI's root semantics so the plugin and `sage-kit` never operate on
 * different task stores: nearest initialized project wins; otherwise a git
 * root (including a linked worktree) owns the state.
 */
export function discoverRoot(start) {
  let current = resolve(start);
  for (;;) {
    if (existsSync(join(current, ".sage-kit", "config.json"))) return current;
    if (existsSync(join(current, ".git"))) return gitProjectRoot(current);
    const parent = dirname(current);
    if (parent === current) return undefined;
    current = parent;
  }
}
