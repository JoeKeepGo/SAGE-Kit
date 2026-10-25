/**
 * Candidate handling and protected-asset checks (Builder/Evaluator boundary).
 *
 * A Builder only hands over data (`CandidateFile[]`); the Evaluator decides
 * whether that data is acceptable and applies it inside an isolated copy. The
 * protected evaluation assets (tests, hidden suites, package/release config,
 * CI config) can never be modified by a candidate (D-012).
 */
import { lstat, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { SageError } from "../core/errors.js";
import { ensureDir, isPathInside, sha256 } from "../core/fs-utils.js";
import type { Candidate, CandidateFile, RsiLimits } from "./types.js";
import { isProtectedPath, normalizeCandidatePath } from "./validate.js";

export type ProtectedManifest = Map<string, string>;

export interface CandidateAssessment {
  /** Candidate files (paths re-normalized/validated). */
  files: CandidateFile[];
  changedFiles: number;
  /** Approximate changed lines (prefix/suffix-trimmed diff; docs §6). */
  changedLines: number;
  /** Protected paths the candidate tries to modify. */
  protectedHits: string[];
  ok: boolean;
  reasonCode?: "E_RSI_PROTECTED_ASSET" | "E_RSI_DIFF_TOO_LARGE";
  reasonMessage?: string;
}

export interface AssessCandidateOptions {
  protectedPaths: readonly string[];
  limits: RsiLimits;
}

function splitLines(text: string): string[] {
  if (text === "") return [];
  return text.replace(/\r\n/g, "\n").split("\n");
}

/**
 * Count changed lines by trimming the common prefix and suffix of the old and
 * new content. This is a deterministic approximation (no LCS), which is what a
 * budget check needs; docs/m3-rsi.md §6 documents the approximation.
 */
export function countChangedLines(before: string | null, after: string | null): number {
  const beforeLines = before === null ? [] : splitLines(before);
  const afterLines = after === null ? [] : splitLines(after);
  let prefix = 0;
  const maxPrefix = Math.min(beforeLines.length, afterLines.length);
  while (prefix < maxPrefix && beforeLines[prefix] === afterLines[prefix]) prefix += 1;
  let suffix = 0;
  while (
    suffix < beforeLines.length - prefix &&
    suffix < afterLines.length - prefix &&
    beforeLines[beforeLines.length - 1 - suffix] === afterLines[afterLines.length - 1 - suffix]
  ) {
    suffix += 1;
  }
  return beforeLines.length - prefix - suffix + (afterLines.length - prefix - suffix);
}

/** Baseline text of a candidate target, or null when absent/not a regular file. */
async function readBaselineText(projectRoot: string, relativePath: string): Promise<string | null> {
  const target = resolve(projectRoot, ...relativePath.split("/"));
  if (!isPathInside(projectRoot, target)) {
    throw new SageError(`Candidate path escapes the project: ${relativePath}`, "E_RSI_UNSAFE_PATH", 2);
  }
  try {
    const info = await lstat(target);
    if (!info.isFile()) return null;
    return await readFile(target, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}

/**
 * Validate a builder's candidate before it is applied. Candidate *content*
 * problems that a human should see (protected asset, over-budget diff) are
 * reported as an assessment result so they are recorded as a failed evaluation;
 * malformed input throws (`E_RSI_BAD_CANDIDATE`/`E_RSI_UNSAFE_PATH`).
 */
export async function assessCandidate(
  projectRoot: string,
  candidate: Candidate,
  options: AssessCandidateOptions,
): Promise<CandidateAssessment> {
  const files = candidate.files.map((file, index) => ({
    path: normalizeCandidatePath(file.path, `candidate.files[${index}].path`),
    content: file.content,
  }));
  let changedLines = 0;
  for (const file of files) {
    const before = await readBaselineText(projectRoot, file.path);
    changedLines += countChangedLines(before, file.content);
  }
  const protectedHits = files
    .map((file) => file.path)
    .filter((path) => isProtectedPath(path, options.protectedPaths))
    .sort();
  const changedFiles = files.length;
  const base: CandidateAssessment = {
    files,
    changedFiles,
    changedLines,
    protectedHits,
    ok: true,
  };
  if (protectedHits.length > 0) {
    return {
      ...base,
      ok: false,
      reasonCode: "E_RSI_PROTECTED_ASSET",
      reasonMessage: `Candidate modifies protected evaluation assets: ${protectedHits.join(", ")}`,
    };
  }
  if (changedFiles > options.limits.maxCandidateFiles) {
    return {
      ...base,
      ok: false,
      reasonCode: "E_RSI_DIFF_TOO_LARGE",
      reasonMessage: `Candidate changes ${changedFiles} files (limit ${options.limits.maxCandidateFiles})`,
    };
  }
  if (changedLines > options.limits.maxChangedLines) {
    return {
      ...base,
      ok: false,
      reasonCode: "E_RSI_DIFF_TOO_LARGE",
      reasonMessage: `Candidate changes ~${changedLines} lines (limit ${options.limits.maxChangedLines})`,
    };
  }
  return base;
}

/**
 * Reject symlinks anywhere on a candidate's path. A candidate must not be able
 * to write through a repository symlink into a protected test file or outside
 * the evaluation worktree.
 */
async function assertNoSymlinkPath(root: string, relativePath: string): Promise<void> {
  const parts = relativePath.split("/");
  let current = root;
  for (const part of parts) {
    current = join(current, part);
    let info;
    try {
      info = await lstat(current);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
      throw error;
    }
    if (info.isSymbolicLink()) {
      throw new SageError(`Candidate path traverses a symlink: ${relativePath}`, "E_RSI_UNSAFE_PATH", 2);
    }
  }
}

/** Apply candidate files inside an isolated workspace copy. */
export async function applyCandidateFiles(workspaceRoot: string, files: readonly CandidateFile[]): Promise<void> {
  const root = resolve(workspaceRoot);
  for (const file of files) {
    const target = resolve(root, ...file.path.split("/"));
    if (!isPathInside(root, target)) {
      throw new SageError(`Candidate path escapes the evaluation workspace: ${file.path}`, "E_RSI_UNSAFE_PATH", 2);
    }
    await assertNoSymlinkPath(root, file.path);
    if (file.content === null) {
      const existing = await lstat(target).catch(() => null);
      if (existing?.isDirectory()) {
        // Deletion is a file operation. Recursively deleting a directory would
        // both under-count the candidate and bypass protected descendants.
        throw new SageError(
          `Candidate deletion target is a directory, not a file: ${file.path}`,
          "E_RSI_UNSAFE_PATH",
          2,
        );
      }
      if (existing) await rm(target, { force: true });
      continue;
    }
    await ensureDir(dirname(target));
    await writeFile(target, file.content, "utf8");
  }
}

async function collectManifest(
  absolutePath: string,
  relativePath: string,
  manifest: ProtectedManifest,
): Promise<void> {
  let info;
  try {
    info = await lstat(absolutePath);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
    throw error;
  }
  if (info.isSymbolicLink()) {
    throw new SageError(
      `Protected evaluation asset is a symlink; refusing to evaluate: ${relativePath}`,
      "E_RSI_PROTECTED_ASSET_SYMLINK",
      2,
    );
  }
  if (info.isDirectory()) {
    const entries = await readdir(absolutePath, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      await collectManifest(join(absolutePath, entry.name), `${relativePath}/${entry.name}`, manifest);
    }
    return;
  }
  if (info.isFile()) {
    manifest.set(relativePath, sha256(await readFile(absolutePath)));
  }
}

/** Hash every protected evaluation asset under the project root. */
export async function hashProtectedAssets(
  projectRoot: string,
  protectedPaths: readonly string[],
): Promise<ProtectedManifest> {
  const manifest: ProtectedManifest = new Map();
  for (const protectedPath of protectedPaths) {
    await collectManifest(resolve(projectRoot, ...protectedPath.split("/")), protectedPath, manifest);
  }
  return manifest;
}

/** Symmetric difference between two protected manifests (relative paths). */
export function diffProtectedManifests(before: ProtectedManifest, after: ProtectedManifest): string[] {
  const changed = new Set<string>();
  for (const [path, hash] of before) {
    if (after.get(path) !== hash) changed.add(path);
  }
  for (const path of after.keys()) {
    if (!before.has(path)) changed.add(path);
  }
  return [...changed].sort();
}
