/**
 * Isolated evaluation workspace.
 *
 * The evaluator never runs tests in the source tree. It copies the project into
 * a fresh OS temp directory, ignoring heavyweight/untracked trees, applies the
 * candidate there and always removes the copy afterwards.
 *
 * The fixed suite therefore cannot mutate the source tree, and the candidate is
 * never applied outside the temporary copy. Real dependency installation /
 * `git worktree` evaluation is NOT implemented in the skeleton (docs/m3-rsi.md
 * §10): default exclusions keep evaluation cheap and offline.
 */
import { cp, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, sep } from "node:path";
import { SageError } from "../core/errors.js";

export const DEFAULT_COPY_EXCLUDE: readonly string[] = [
  ".git",
  ".sage-kit",
  ".dsh",
  "node_modules",
  "dist",
  "work",
  "coverage",
  "reports",
];

export interface TempProjectCopy {
  /** Temporary root that holds the copy; removed by `cleanup()`. */
  tempRoot: string;
  /** Root of the copied project (the fixed command's cwd). */
  projectRoot: string;
  /**
   * Remove the temporary copy. Returns true when it is gone (including when it
   * was already absent); false when removal failed.
   */
  cleanup(): Promise<boolean>;
}

export interface CreateWorkspaceOptions {
  /** Extra top-level directory names to exclude from the copy. */
  exclude?: readonly string[];
}

export async function createEvaluationWorkspace(
  sourceRoot: string,
  options: CreateWorkspaceOptions = {},
): Promise<TempProjectCopy> {
  const excluded = new Set([...DEFAULT_COPY_EXCLUDE, ...(options.exclude ?? [])]);
  let tempRoot: string;
  try {
    tempRoot = await mkdtemp(join(tmpdir(), "sage-kit-rsi-eval-"));
  } catch (error) {
    throw new SageError(
      `Cannot create RSI evaluation workspace: ${(error as Error).message}`,
      "E_RSI_WORKSPACE_FAILED",
      1,
    );
  }
  const projectRoot = join(tempRoot, "project");
  try {
    await cp(sourceRoot, projectRoot, {
      recursive: true,
      filter: (source: string): boolean => {
        if (source === sourceRoot) return true;
        const rel = relative(sourceRoot, source);
        if (!rel) return true;
        const topLevel = rel.split(sep)[0] as string;
        return !excluded.has(topLevel);
      },
    });
  } catch (error) {
    await rm(tempRoot, { recursive: true, force: true }).catch(() => undefined);
    throw new SageError(
      `Cannot copy project into RSI evaluation workspace: ${(error as Error).message}`,
      "E_RSI_WORKSPACE_FAILED",
      1,
    );
  }
  return {
    tempRoot,
    projectRoot,
    cleanup: async (): Promise<boolean> => {
      try {
        await rm(tempRoot, { recursive: true, force: true });
        return true;
      } catch {
        return false;
      }
    },
  };
}
