/**
 * Pure helpers shared by the DSH plugin. Kept free of DSH imports so they can
 * be unit-tested without installing the host runtime.
 */
import { existsSync } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";

export const DEFAULT_BRIEF_BYTES = 2048;
export const MIN_BRIEF_BYTES = 256;
export const MAX_BRIEF_BYTES = 8192;

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

export function discoverRoot(start) {
  let current = resolve(start);
  for (;;) {
    if (existsSync(join(current, ".sage-kit", "config.json"))) return current;
    const parent = dirname(current);
    if (parent === current) return undefined;
    current = parent;
  }
}
