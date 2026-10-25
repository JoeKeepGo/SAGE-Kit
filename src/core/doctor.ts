import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { detectAdapters, getAdapter } from "../adapters/index.js";
import type { HostDetection } from "../adapters/types.js";
import { exists, readJsonFile, fileSize } from "./fs-utils.js";
import { loadConfig } from "./config.js";
import { SageError, toSageError } from "./errors.js";
import { homeDirectory, statePaths } from "./paths.js";
import { recoverStaleRuns } from "./runs.js";

export interface DoctorCheck {
  name: string;
  status: "ok" | "warn" | "error";
  detail: string;
}

export interface DoctorResult {
  ok: boolean;
  checks: DoctorCheck[];
  configPath: string;
  projectRoot: string;
}

// P0 policy: Node.js >=22 (see package.json engines and docs/decisions.md D-014).
export function checkNode(version: string = process.versions.node): DoctorCheck {
  const major = Number(version.split(".")[0] ?? 0);
  const ok = Number.isFinite(major) && major >= 22;
  return {
    name: "node",
    status: ok ? "ok" : "error",
    detail: `Node ${version}${ok ? "" : " (need >=22)"}`,
  };
}

export async function runDoctor(
  projectRoot: string,
  env: NodeJS.ProcessEnv = process.env,
  home = homeDirectory(env),
): Promise<DoctorResult> {
  const checks: DoctorCheck[] = [checkNode()];
  const paths = statePaths(projectRoot);
  let config;
  try {
    config = await loadConfig(paths);
  } catch (error) {
    const sage = toSageError(error);
    checks.push({ name: "config", status: "error", detail: sage.message });
    return { ok: false, checks, configPath: paths.config, projectRoot };
  }
  if (!config) {
    checks.push({ name: "config", status: "error", detail: `not initialized (${paths.config} missing)` });
    return { ok: false, checks, configPath: paths.config, projectRoot };
  }
  checks.push({ name: "config", status: "ok", detail: `${config.host}/${config.scope} at ${paths.config}` });

  const adapter = getAdapter(config.host);
  const expected = adapter.skillTarget(config.scope, config.projectRoot, env, home);
  if (expected && join(expected) !== join(config.skill.path)) {
    checks.push({ name: "skill-path", status: "warn", detail: `config=${config.skill.path} expected=${expected}` });
  }
  if (await exists(config.skill.path)) {
    try {
      const entries = await readdir(config.skill.path);
      checks.push({ name: "skill", status: "ok", detail: `${config.skill.path} (${entries.length} entries)` });
    } catch (error) {
      checks.push({ name: "skill", status: "error", detail: (error as Error).message });
    }
  } else {
    checks.push({ name: "skill", status: "error", detail: `missing ${config.skill.path}` });
  }

  const pathsToCheck = adapter.diagnosticPaths(config.projectRoot, env, home);
  const present = [];
  for (const path of pathsToCheck) if (await exists(path)) present.push(path);
  if (present.length > 1) {
    checks.push({ name: "skill-duplicates", status: "warn", detail: present.join(", ") });
  } else {
    checks.push({ name: "skill-duplicates", status: "ok", detail: present.join(", ") || "none" });
  }

  let detections: HostDetection[] = [];
  try {
    detections = await detectAdapters(env, home, config.projectRoot);
  } catch (error) {
    checks.push({ name: "host", status: "warn", detail: (error as Error).message });
  }
  const detected = detections.find((item) => item.host === config.host);
  if (detected?.found) {
    checks.push({ name: "host", status: "ok", detail: `${config.host} found (${detected.evidence.join(", ")})` });
  } else {
    checks.push({ name: "host", status: "warn", detail: `${config.host} not detected` });
  }
  for (const note of detected?.notes ?? []) checks.push({ name: "host-note", status: "warn", detail: note });

  if (await exists(paths.tasksDir)) {
    const names = (await readdir(paths.tasksDir)).filter((name) => name.endsWith(".json"));
    let bad = 0;
    for (const name of names) {
      try {
        const task = await readJsonFile<{ schemaVersion?: number; id?: string; status?: string }>(join(paths.tasksDir, name));
        if (task.schemaVersion !== 1 || !task.id || !task.status) bad += 1;
      } catch {
        bad += 1;
      }
    }
    checks.push({
      name: "tasks",
      status: bad ? "error" : "ok",
      detail: `${names.length} files, ${bad} invalid`,
    });
  } else {
    checks.push({ name: "tasks", status: "warn", detail: `missing ${paths.tasksDir}` });
  }

  try {
    const { recovered, taskChanges, errors } = await recoverStaleRuns(paths);
    const changed = taskChanges.map((change) => `${change.taskId}: ${change.from} -> ${change.to}`);
    checks.push({
      name: "runs",
      status: recovered.length || taskChanges.length || errors.length ? "warn" : "ok",
      detail: [
        recovered.length ? `recovered ${recovered.length} stale run(s)` : "no stale runs",
        `${taskChanges.length} task change(s)${changed.length ? ` (${changed.join(", ")})` : ""}`,
        ...errors,
      ].join("; "),
    });
  } catch (error) {
    checks.push({ name: "runs", status: "warn", detail: (error as Error).message });
  }

  const eventsPath = join(paths.eventsDir, "events.jsonl");
  if (await exists(eventsPath)) {
    checks.push({ name: "events", status: "ok", detail: `${await fileSize(eventsPath)} bytes` });
  } else {
    checks.push({ name: "events", status: "warn", detail: "no events recorded yet" });
  }

  return {
    ok: checks.every((check) => check.status !== "error"),
    checks,
    configPath: paths.config,
    projectRoot,
  };
}

export function formatDoctor(result: DoctorResult): string {
  const lines = [`SAGE-Kit doctor: ${result.ok ? "OK" : "FAILED"}`, `project: ${result.projectRoot}`, `config: ${result.configPath}`];
  for (const check of result.checks) lines.push(`[${check.status}] ${check.name}: ${check.detail}`);
  return lines.join("\n");
}

export async function detectHosts(projectRoot: string, env: NodeJS.ProcessEnv = process.env, home = "") {
  const detections = await detectAdapters(env, home, projectRoot);
  let config = null;
  try {
    config = await loadConfig(statePaths(projectRoot));
  } catch (error) {
    if (!(error instanceof SageError)) throw error;
  }
  return { detections, config };
}
