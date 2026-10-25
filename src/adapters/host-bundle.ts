import { copyFile, lstat, readdir, rmdir } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { SageError } from "../core/errors.js";
import {
  ensureDir,
  exists,
  isPathInside,
  nowIso,
  readText,
  removePath,
  writeJsonAtomic,
} from "../core/fs-utils.js";

/**
 * File-level host bundles for Codex/Claude.
 *
 * A bundle is a small marketplace tree staged inside the project:
 *
 *   .sage-kit/hosts/<host>/...
 *
 * The canonical Skill is copied from `skills/sage-kit` (installed artifact, not
 * a second source of truth) because Codex plugin manifests may only reference
 * Skill roots under the plugin root. The host's own CLI still performs the
 * registration step (`codex plugin marketplace add <path>`); SAGE-Kit never
 * edits host config files directly.
 *
 * Every staged file is recorded in a marker file so uninstall can remove only
 * files this install created and leave user content untouched.
 */

export const HOST_BUNDLE_MARKER = ".sage-kit-host-bundle.json";
const BUNDLE_SCHEMA_VERSION = 1;
const PLUGIN_RELATIVE_DIR = "plugins";

export interface HostBundleSpec {
  host: string;
  bundleRoot: string;
  pluginName: string;
  /** Directory holding the thin plugin template (manifest + hooks), absolute. */
  pluginSource: string;
  /** Manifest path inside the plugin template, OS separators. */
  pluginManifestPath: string;
  /** Marketplace manifest path relative to `bundleRoot`, OS separators. */
  marketplacePath: string;
  /** Marketplace document; host specific. */
  marketplace: Record<string, unknown>;
  /** Canonical Skill source directory, absolute. */
  skillSource: string;
  /** Skill path relative to the staged plugin root, OS separators. */
  skillRelativePath: string;
  version: string;
  force?: boolean;
}

export interface HostBundlePaths {
  bundleRoot: string;
  marketplaceRoot: string;
  pluginRoot: string;
  skillPath: string;
  marketplacePath: string;
}

export interface HostBundleInstallOptions {
  projectRoot?: string;
  packageRoot?: string;
  version?: string;
  force?: boolean;
}

export interface HostBundleInstallResult extends HostBundlePaths {
  host: string;
  pluginName: string;
  marketplaceName: string;
  version: string;
  files: string[];
  created: boolean;
  warnings: string[];
}

export interface HostBundleUninstallOptions {
  bundleRoot: string;
  host?: string;
}

export interface HostBundleUninstallResult {
  removed: string[];
  kept: string[];
  warnings: string[];
}

interface HostBundleMarker {
  schemaVersion: number;
  host: string;
  pluginName: string;
  version: string;
  files: string[];
  /** Intended new destinations; not owned until their write succeeds. */
  pendingFiles?: string[];
  createdAt: string;
  updatedAt: string;
}

function toPosix(value: string): string {
  return value.split(sep).join("/");
}

function pluginRootFor(bundleRoot: string, pluginName: string): string {
  return join(bundleRoot, PLUGIN_RELATIVE_DIR, pluginName);
}

export function hostBundlePaths(spec: Pick<HostBundleSpec, "bundleRoot" | "pluginName" | "skillRelativePath" | "marketplacePath">): HostBundlePaths {
  const pluginRoot = pluginRootFor(spec.bundleRoot, spec.pluginName);
  return {
    bundleRoot: spec.bundleRoot,
    marketplaceRoot: spec.bundleRoot,
    pluginRoot,
    skillPath: join(pluginRoot, spec.skillRelativePath),
    marketplacePath: join(spec.bundleRoot, spec.marketplacePath),
  };
}

async function readMarker(bundleRoot: string): Promise<HostBundleMarker | null> {
  const markerPath = join(bundleRoot, HOST_BUNDLE_MARKER);
  if (!(await exists(markerPath))) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(await readText(markerPath));
  } catch {
    throw new SageError(`Host bundle marker is not valid JSON: ${markerPath}`, "E_HOST_BUNDLE_MARKER", 1);
  }
  const marker = parsed as Partial<HostBundleMarker>;
  if (
    !marker ||
    marker.schemaVersion !== BUNDLE_SCHEMA_VERSION ||
    typeof marker.host !== "string" ||
    !Array.isArray(marker.files) ||
    !marker.files.every((item) => typeof item === "string")
  ) {
    throw new SageError(`Host bundle marker is not supported: ${markerPath}`, "E_HOST_BUNDLE_MARKER", 1);
  }
  return marker as HostBundleMarker;
}

async function listSourceFiles(root: string): Promise<string[]> {
  const base = resolve(root);
  const files: string[] = [];
  async function walk(dir: string): Promise<void> {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const target = join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(target);
      } else if (entry.isFile()) {
        files.push(toPosix(relative(base, target)));
      }
    }
  }
  await walk(base);
  return files.sort();
}

/**
 * Refuse to write through an existing symlink/junction at or above `target`.
 * Lexical containment alone is insufficient: `plugins/<name>/hooks` could be a
 * link to a user directory outside the bundle.
 */
async function assertSafeTarget(bundleRoot: string, target: string): Promise<void> {
  const base = resolve(bundleRoot);
  const dest = resolve(target);
  if (!isPathInside(base, dest)) {
    throw new SageError(`Refusing a host bundle path outside its root: ${dest}`, "E_HOST_BUNDLE_ESCAPE", 1);
  }
  const rootInfo = await lstat(base).catch(() => null);
  if (rootInfo?.isSymbolicLink()) {
    throw new SageError(`Refusing a symlinked host bundle root: ${base}`, "E_HOST_BUNDLE_ESCAPE", 1);
  }
  let current = base;
  for (const part of relative(base, dest).split(sep).filter(Boolean)) {
    current = join(current, part);
    const info = await lstat(current).catch(() => null);
    if (!info) return;
    if (info.isSymbolicLink()) {
      throw new SageError(`Refusing a host bundle path that traverses a symlink: ${current}`, "E_HOST_BUNDLE_ESCAPE", 1);
    }
    if (!info.isDirectory() && current !== dest) {
      throw new SageError(`Host bundle path ancestor is not a directory: ${current}`, "E_HOST_BUNDLE_ESCAPE", 1);
    }
  }
}

/** Refuse links at `.sage-kit` / `.sage-kit/hosts`, above the bundle root. */
async function assertSafeBundleAncestors(bundleRoot: string): Promise<void> {
  const hostsRoot = dirname(resolve(bundleRoot));
  const stateRoot = dirname(hostsRoot);
  for (const candidate of [stateRoot, hostsRoot]) {
    const info = await lstat(candidate).catch(() => null);
    if (!info) continue;
    if (info.isSymbolicLink()) {
      throw new SageError(
        `Refusing a host bundle whose ancestor is a symlink: ${candidate}`,
        "E_HOST_BUNDLE_ESCAPE",
        1,
      );
    }
    if (!info.isDirectory()) {
      throw new SageError(
        `Refusing a host bundle whose ancestor is not a directory: ${candidate}`,
        "E_HOST_BUNDLE_ESCAPE",
        1,
      );
    }
  }
}

/** Every remaining directory entry, including symlinks; never followed. */
async function listEntriesRelative(root: string): Promise<string[]> {
  const base = resolve(root);
  const entriesOut: string[] = [];
  async function walk(dir: string): Promise<void> {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const target = join(dir, entry.name);
      entriesOut.push(toPosix(relative(base, target)));
      if (entry.isDirectory()) await walk(target);
    }
  }
  await walk(base);
  return entriesOut.sort();
}

async function pruneEmptyDirs(bundleRoot: string, startDir: string): Promise<void> {
  const stop = resolve(bundleRoot);
  let dir = resolve(startDir);
  while (dir !== stop && isPathInside(stop, dir)) {
    const entries = await readdir(dir).catch(() => null);
    if (!entries || entries.length > 0) return;
    await rmdir(dir);
    dir = dirname(dir);
  }
}

/**
 * Stage (or refresh) a host bundle. Re-running is idempotent: files are
 * overwritten, stale owned files are removed, and user-added files are kept.
 * A directory without our marker is never adopted unless `force` is set.
 */
export async function installHostBundle(spec: HostBundleSpec): Promise<HostBundleInstallResult> {
  const pluginSource = resolve(spec.pluginSource);
  const manifestSource = join(pluginSource, spec.pluginManifestPath);
  const skillSource = resolve(spec.skillSource);
  if (!(await exists(join(skillSource, "SKILL.md")))) {
    throw new SageError(`Skill source is missing SKILL.md: ${skillSource}`, "E_SKILL_SOURCE", 1);
  }
  if (!(await exists(manifestSource))) {
    throw new SageError(
      `Host bundle template is missing ${spec.pluginManifestPath}: ${pluginSource}`,
      "E_HOST_BUNDLE_SOURCE",
      1,
    );
  }

  const paths = hostBundlePaths(spec);
  await assertSafeBundleAncestors(spec.bundleRoot);
  const existed = await exists(spec.bundleRoot);
  let previous: HostBundleMarker | null = null;
  const warnings: string[] = [];
  if (existed) {
    previous = await readMarker(spec.bundleRoot);
    if (!previous) {
      let entries: string[];
      try {
        entries = await readdir(spec.bundleRoot);
      } catch (error) {
        throw new SageError(
          `Cannot read the existing host bundle directory: ${spec.bundleRoot}: ${String(error)}`,
          "E_HOST_BUNDLE_UNREADABLE",
          1,
        );
      }
      if (entries.length > 0 && !spec.force) {
        throw new SageError(
          `Refusing to overwrite an unowned host bundle directory: ${spec.bundleRoot} (remove it or pass force)`,
          "E_HOST_BUNDLE_UNOWNED",
          1,
        );
      }
      if (entries.length > 0) warnings.push(`Adopted a pre-existing host bundle directory because force was set: ${spec.bundleRoot}`);
    } else if (previous.host !== spec.host) {
      throw new SageError(
        `Host bundle at ${spec.bundleRoot} belongs to ${previous.host}, not ${spec.host}`,
        "E_HOST_BUNDLE_INCOMPATIBLE",
        1,
      );
    }
  }

  // Ownership is derived only from the source templates, never from the
  // destination tree. A user file under plugins/<name>/ must not become ours
  // just because it happens to be present during a reinstall.
  const pluginSourceFiles = await listSourceFiles(pluginSource);
  const skillSourceFiles = await listSourceFiles(skillSource);
  const sources = new Map<string, string>();
  for (const file of pluginSourceFiles) {
    sources.set(toPosix(join(PLUGIN_RELATIVE_DIR, spec.pluginName, file)), join(pluginSource, file));
  }
  for (const file of skillSourceFiles) {
    sources.set(toPosix(join(PLUGIN_RELATIVE_DIR, spec.pluginName, spec.skillRelativePath, file)), join(skillSource, file));
  }
  const files = new Set(sources.keys());
  files.add(toPosix(spec.marketplacePath));

  for (const file of files) {
    const target = resolve(spec.bundleRoot, file);
    await assertSafeTarget(spec.bundleRoot, target);
    // Source-derived ownership describes what this version intends to write,
    // not what already exists at the destination. A user file that happens to
    // occupy a path introduced by a newer template must not be silently
    // overwritten (and later deleted as "owned") unless the caller explicitly
    // force-adopts the directory.
    if (!previous?.files.includes(file)) {
      const info = await lstat(target).catch(() => null);
      if (info) {
        if (!spec.force) {
          throw new SageError(
            `Refusing to overwrite an existing unowned host bundle file: ${target} (remove it or pass force)`,
            "E_HOST_BUNDLE_UNOWNED",
            1,
          );
        }
        warnings.push(`Adopted an existing host bundle file because force was set: ${target}`);
      }
    }
  }

  // Pending destinations are not ownership. Persist each completed file so a
  // failed copy cannot authorize overwriting/deleting a later user-created file.
  const now = nowIso();
  const ownedFiles = new Set(previous?.files ?? []);
  const marker: HostBundleMarker = {
    schemaVersion: BUNDLE_SCHEMA_VERSION,
    host: spec.host,
    pluginName: spec.pluginName,
    version: spec.version,
    files: [...ownedFiles].sort(),
    pendingFiles: [...files].filter((file) => !ownedFiles.has(file)).sort(),
    createdAt: previous?.createdAt ?? now,
    updatedAt: now,
  };
  const markerPath = join(spec.bundleRoot, HOST_BUNDLE_MARKER);
  await writeJsonAtomic(markerPath, marker);

  const manifestFile = toPosix(join(PLUGIN_RELATIVE_DIR, spec.pluginName, spec.pluginManifestPath));
  for (const file of files) {
    const target = resolve(spec.bundleRoot, file);
    if (file === toPosix(spec.marketplacePath)) {
      await writeJsonAtomic(target, spec.marketplace);
    } else if (file === manifestFile) {
      const manifest = JSON.parse(await readText(manifestSource)) as Record<string, unknown>;
      manifest.version = spec.version;
      await writeJsonAtomic(target, manifest);
    } else {
      await ensureDir(dirname(target));
      await copyFile(sources.get(file) as string, target);
    }
    ownedFiles.add(file);
    marker.files = [...ownedFiles].sort();
    marker.pendingFiles = marker.pendingFiles?.filter((pending) => pending !== file);
    marker.updatedAt = nowIso();
    await writeJsonAtomic(markerPath, marker);
  }

  if (previous) {
    for (const file of previous.files) {
      if (files.has(file)) continue;
      const target = resolve(spec.bundleRoot, file);
      if (!isPathInside(spec.bundleRoot, target)) {
        warnings.push(`Skipped stale owned file outside the bundle root: ${file}`);
        continue;
      }
      try {
        await assertSafeTarget(spec.bundleRoot, target);
      } catch (error) {
        warnings.push(`Skipped stale owned path that escaped through a link: ${file} (${String(error)})`);
        continue;
      }
      const info = await lstat(target).catch(() => null);
      if (info?.isDirectory()) {
        warnings.push(`Skipped a directory recorded as a stale file: ${file}`);
        continue;
      }
      if (info) await removePath(target);
      await pruneEmptyDirs(spec.bundleRoot, dirname(target));
    }
  }

  // A successful refresh owns only the current files; failed refreshes retain
  // completed ownership plus the previous files for retry/uninstall cleanup.
  await writeJsonAtomic(join(spec.bundleRoot, HOST_BUNDLE_MARKER), {
    ...marker,
    files: [...files].sort(),
    updatedAt: nowIso(),
  });

  return {
    ...paths,
    host: spec.host,
    pluginName: spec.pluginName,
    marketplaceName: typeof spec.marketplace.name === "string" ? spec.marketplace.name : spec.pluginName,
    version: spec.version,
    files: [...files].sort(),
    created: previous === null,
    warnings,
  };
}

/**
 * Remove only files recorded in the bundle marker. User files, host
 * registrations (for example Codex config entries) and project state are left
 * untouched; deleting an already-uninstalled bundle is a no-op.
 */
export async function uninstallHostBundle(
  options: HostBundleUninstallOptions,
): Promise<HostBundleUninstallResult> {
  const { bundleRoot, host: expectedHost } = options;
  if (!(await exists(bundleRoot))) {
    return { removed: [], kept: [], warnings: [] };
  }
  try {
    await assertSafeBundleAncestors(bundleRoot);
  } catch (error) {
    return { removed: [], kept: [], warnings: [String(error)] };
  }
  const rootInfo = await lstat(bundleRoot).catch(() => null);
  if (rootInfo?.isSymbolicLink()) {
    return {
      removed: [],
      kept: [],
      warnings: [`Refusing to uninstall a symlinked host bundle root: ${bundleRoot}`],
    };
  }
  let marker: HostBundleMarker | null;
  try {
    marker = await readMarker(bundleRoot);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { removed: [], kept: [], warnings: [`Host bundle marker could not be read; left it untouched: ${message}`] };
  }
  if (!marker) {
    const files = await listEntriesRelative(bundleRoot);
    return {
      removed: [],
      kept: files.map((file) => join(bundleRoot, file)),
      warnings: [`No SAGE-Kit host bundle marker found; left it untouched: ${bundleRoot}`],
    };
  }
  if (expectedHost && marker.host !== expectedHost) {
    return {
      removed: [],
      kept: await listEntriesRelative(bundleRoot).then((files) => files.map((file) => join(bundleRoot, file))),
      warnings: [`Host bundle belongs to ${marker.host}, not ${expectedHost}; left it untouched: ${bundleRoot}`],
    };
  }

  const removed: string[] = [];
  const warnings: string[] = [];
  const removedDirs = new Set<string>();
  for (const file of [...marker.files].reverse()) {
    const target = resolve(bundleRoot, file);
    if (!isPathInside(bundleRoot, target)) {
      warnings.push(`Refusing to remove a path outside the bundle root: ${file}`);
      continue;
    }
    try {
      await assertSafeTarget(bundleRoot, target);
    } catch (error) {
      warnings.push(`Skipped an owned path that escaped through a link: ${file} (${String(error)})`);
      continue;
    }
    const info = await lstat(target).catch(() => null);
    if (!info) continue;
    if (info.isDirectory()) {
      // Old bundles may have recorded a directory; never recurse blindly.
      warnings.push(`Skipped a directory recorded as a file: ${file}`);
      continue;
    }
    await removePath(target);
    removed.push(target);
    removedDirs.add(dirname(target));
  }
  for (const dir of [...removedDirs].sort((left, right) => right.length - left.length)) {
    await pruneEmptyDirs(bundleRoot, dir);
  }

  const markerPath = join(bundleRoot, HOST_BUNDLE_MARKER);
  try {
    await assertSafeTarget(bundleRoot, markerPath);
    if (await exists(markerPath)) await removePath(markerPath);
    removed.push(markerPath);
  } catch (error) {
    warnings.push(`Skipped marker removal through a link: ${String(error)}`);
  }

  const kept = (await listEntriesRelative(bundleRoot)).map((file) => join(bundleRoot, file));
  if (kept.length === 0) {
    const remaining = await readdir(bundleRoot).catch(() => null);
    if (remaining === null) {
      warnings.push(`Could not confirm that the host bundle root is empty; left it in place: ${bundleRoot}`);
    } else if (remaining.length === 0) {
      await rmdir(bundleRoot);
      removed.push(bundleRoot);
    } else {
      warnings.push(`Host bundle root still has entries; left it in place: ${bundleRoot}`);
    }
  } else {
    warnings.push(`Kept files not owned by this SAGE-Kit host bundle: ${kept.join(", ")}`);
  }
  return { removed, kept, warnings };
}
