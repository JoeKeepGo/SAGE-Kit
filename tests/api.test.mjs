/**
 * Contract tests for the host-neutral library surface (`src/index.ts`).
 *
 * The CLI stays the primary product surface; these tests pin the additional
 * `import("sage-kit")` API used by host adapters (for example the DSH plugin)
 * and prove that both surfaces share the same file-mode state.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { after, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import * as api from "sage-kit";

const REPO_ROOT = fileURLToPath(new URL("..", import.meta.url));
const CLI = fileURLToPath(new URL("../dist/cli.js", import.meta.url));
const DIST_INDEX = join(REPO_ROOT, "dist", "index.js");
const DIST_TYPES = join(REPO_ROOT, "dist", "index.d.ts");
const PACKAGE_JSON = JSON.parse(await readFile(join(REPO_ROOT, "package.json"), "utf8"));
const PACKAGE_VERSION = PACKAGE_JSON.version;
const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const cleanups = [];
await mkdir(TEST_TMP_BASE, { recursive: true });

const EXPECTED_RUNTIME_EXPORTS = [
  "SageError",
  "TASK_STATUSES",
  "buildBrief",
  "checkRsiGate",
  "configExists",
  "createTask",
  "ensureStateDirs",
  "findActiveTask",
  "findProjectRoot",
  "homeDirectory",
  "isTaskStatus",
  "listTasks",
  "listTasksStrict",
  "loadConfig",
  "readTask",
  "setTaskWorktree",
  "statePaths",
  "updateTaskStatus",
].sort();
const EXPECTED_STATUSES = [
  "imported",
  "ready",
  "running",
  "review",
  "done",
  "blocked",
  "failed",
  "cancelled",
  "interrupted",
];

function runProcess(command, args, cwd, options = {}) {
  const timeoutMs = options.timeoutMs ?? 60_000;
  return new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, NO_COLOR: "1", ...(options.env ?? {}) },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs);
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolvePromise({ code, stdout, stderr });
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.stdin.end("");
  });
}

function runCli(cwd, args) {
  return runProcess(process.execPath, [CLI, ...args], cwd);
}

async function tempDir() {
  const dir = await mkdtemp(join(TEST_TMP_BASE, "sage-kit-api-"));
  cleanups.push(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

/** Matches an ISO-8601 timestamp string (Date.parse accepts the format). */
function assertIso(value, label) {
  assert.equal(typeof value, "string", `${label} must be a string`);
  assert.equal(Number.isNaN(Date.parse(value)), false, `${label} must be a valid timestamp: ${value}`);
}

/** assert.rejects predicate for a specific SageError code. */
function sageError(code) {
  return (error) => {
    assert.ok(error instanceof api.SageError, `expected SageError, got ${error?.constructor?.name}`);
    assert.equal(error.code, code);
    return true;
  };
}

async function writeJson(path, value) {
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

after(async () => {
  for (const cleanup of cleanups.reverse()) await cleanup().catch(() => {});
});

describe("SAGE-Kit library API (src/index.ts)", () => {
  it("API-1: exports the documented runtime contract", () => {
    assert.deepEqual(Object.keys(api).sort(), EXPECTED_RUNTIME_EXPORTS);
    assert.deepEqual([...api.TASK_STATUSES], EXPECTED_STATUSES);
    for (const name of EXPECTED_RUNTIME_EXPORTS) {
      if (name === "TASK_STATUSES") continue;
      assert.equal(typeof api[name], "function", `${name} must be a function`);
    }
    assert.ok(api.SageError.prototype instanceof Error);
    const error = new api.SageError("boom", "E_BOOM", 2);
    assert.equal(error.name, "SageError");
    assert.equal(error.message, "boom");
    assert.equal(error.code, "E_BOOM");
    assert.equal(error.exitCode, 2);
    assert.equal(api.isTaskStatus("running"), true);
    assert.equal(api.isTaskStatus("done"), true);
    assert.equal(api.isTaskStatus("not-a-status"), false);
  });

  it("API-2: resolves import(\"sage-kit\") through package exports to built dist", async () => {
    // Self-reference: the test file lives inside the package, so Node resolves
    // the bare specifier through package.json "exports", not node_modules.
    assert.equal(fileURLToPath(import.meta.resolve("sage-kit")), DIST_INDEX);
    assert.equal(PACKAGE_JSON.main, "dist/index.js");
    assert.equal(PACKAGE_JSON.types, "dist/index.d.ts");
    assert.equal(PACKAGE_JSON.exports?.["."]?.import, "./dist/index.js");
    assert.equal(PACKAGE_JSON.exports?.["."]?.types, "./dist/index.d.ts");
    assert.equal(PACKAGE_JSON.exports?.["./package.json"], "./package.json");
    assert.ok(existsSync(DIST_INDEX), "dist/index.js must be built before tests run");
    const declarations = await readFile(DIST_TYPES, "utf8");
    for (const type of [
      "CreateTaskInput",
      "Task",
      "TaskEvidence",
      "TaskStatus",
      "UpdateTaskOptions",
      "BriefResult",
      "StatePaths",
      "SageConfig",
    ]) {
      assert.match(declarations, new RegExp(`\\b${type}\\b`), `dist/index.d.ts must declare ${type}`);
    }
  });

  it("API-3: task create/list/read/status round-trip through the library", async () => {
    const root = await tempDir();
    const paths = api.statePaths(root);
    await api.ensureStateDirs(paths);

    const created = await api.createTask(paths, {
      id: "task-api-0001",
      title: "Library task",
      description: "Created through the library API",
      acceptance: ["node --test tests/api.test.mjs passes"],
      status: "ready",
    });
    assert.equal(created.schemaVersion, 1);
    assert.equal(created.id, "task-api-0001");
    assert.equal(created.title, "Library task");
    assert.equal(created.description, "Created through the library API");
    assert.equal(created.status, "ready");
    assert.deepEqual(created.acceptance, ["node --test tests/api.test.mjs passes"]);
    assert.deepEqual(created.evidence, []);
    assertIso(created.createdAt, "createdAt");
    assertIso(created.updatedAt, "updatedAt");

    // The library writes the same file-mode task JSON the CLI reads.
    const onDisk = JSON.parse(await readFile(join(paths.tasksDir, "task-api-0001.json"), "utf8"));
    assert.deepEqual(onDisk, created);
    assert.deepEqual(await api.listTasks(paths), [created]);
    assert.deepEqual(await api.readTask(paths, "task-api-0001"), created);

    await assert.rejects(
      api.createTask(paths, { id: "task-api-0001", title: "Duplicate" }),
      sageError("E_TASK_EXISTS"),
    );
    await assert.rejects(api.readTask(paths, "task-api-missing"), sageError("E_TASK_NOT_FOUND"));
    const emptyRoot = await tempDir();
    assert.deepEqual(await api.listTasks(api.statePaths(emptyRoot)), []);

    const running = await api.updateTaskStatus(paths, "task-api-0001", "running");
    assert.equal(running.status, "running");
    const review = await api.updateTaskStatus(paths, "task-api-0001", "review");
    assert.equal(review.status, "review");
    await assert.rejects(
      api.updateTaskStatus(paths, "task-api-0001", "done"),
      sageError("E_DONE_WITHOUT_EVIDENCE"),
    );
    const done = await api.updateTaskStatus(paths, "task-api-0001", "done", {
      evidence: ["node --test tests/api.test.mjs passes"],
      note: "verified through the library",
      source: "api-test",
    });
    assert.equal(done.status, "done");
    assert.equal(done.evidence.length, 1);
    assert.equal(done.evidence[0].note, "node --test tests/api.test.mjs passes");
    assert.equal(done.evidence[0].source, "api-test");
    assertIso(done.evidence[0].at, "evidence.at");
    await assert.rejects(
      api.updateTaskStatus(paths, "task-api-0001", "running"),
      sageError("E_BAD_TRANSITION"),
    );

    const attached = await api.setTaskWorktree(paths, "task-api-0001", {
      branch: "sage-kit/task-api-0001",
      worktree: join(root, "worktrees", "task-api-0001"),
    });
    assert.equal(attached.branch, "sage-kit/task-api-0001");
    assert.equal(attached.worktree, join(root, "worktrees", "task-api-0001"));
    const detached = await api.setTaskWorktree(paths, "task-api-0001", null);
    assert.equal(detached.branch, undefined);
    assert.equal(detached.worktree, undefined);

    const activeRoot = await tempDir();
    const activePaths = api.statePaths(activeRoot);
    await api.ensureStateDirs(activePaths);
    await api.createTask(activePaths, { id: "task-api-ready", title: "Ready", status: "ready" });
    await api.createTask(activePaths, { id: "task-api-running", title: "Running", status: "running" });
    const active = api.findActiveTask(await api.listTasks(activePaths));
    assert.equal(active?.id, "task-api-running");
    assert.equal(api.findActiveTask([]), undefined);
  });

  it("API-4: brief renders task/active-task briefs and enforces the byte budget", async () => {
    const root = await tempDir();
    const paths = api.statePaths(root);
    await api.ensureStateDirs(paths);

    const empty = await api.buildBrief(paths);
    assert.equal(empty.taskId, undefined);
    assert.equal(empty.truncated, false);
    assert.match(empty.text, /^# SAGE-Kit brief/);
    assert.match(empty.text, /No task exists yet\./);

    await api.createTask(paths, {
      id: "task-api-brief",
      title: "Brief task",
      acceptance: ["acceptance one", "acceptance two"],
      status: "running",
    });
    const brief = await api.buildBrief(paths, "task-api-brief");
    assert.equal(brief.taskId, "task-api-brief");
    assert.equal(brief.truncated, false);
    assert.match(brief.text, /Task: task-api-brief/);
    assert.match(brief.text, /Title: Brief task/);
    assert.match(brief.text, /Status: running/);
    assert.match(brief.text, /- acceptance one/);
    assert.match(brief.text, /Rules:/);
    assert.ok(Buffer.byteLength(brief.text, "utf8") <= 2048);

    // Without a task id the active task (running) is selected.
    assert.equal((await api.buildBrief(paths)).taskId, "task-api-brief");
    await api.createTask(paths, { id: "task-api-review", title: "Review task", status: "review" });
    assert.equal((await api.buildBrief(paths)).taskId, "task-api-brief");

    const small = await api.buildBrief(paths, "task-api-brief", 256);
    assert.ok(Buffer.byteLength(small.text, "utf8") <= 256);
    assert.equal(small.truncated, true);
    assert.ok(small.text.endsWith("…[truncated]"));
    assert.equal(small.text.includes("\uFFFD"), false);

    await assert.rejects(api.buildBrief(paths, "task-api-missing"), sageError("E_TASK_NOT_FOUND"));
  });

  it("API-5: statePaths/loadConfig/configExists/findProjectRoot/homeDirectory", async () => {
    const root = await tempDir();
    const paths = api.statePaths(root);
    assert.equal(paths.projectRoot, root);
    assert.equal(paths.stateDir, join(root, ".sage-kit"));
    assert.equal(paths.config, join(root, ".sage-kit", "config.json"));
    assert.equal(paths.tasksDir, join(root, ".sage-kit", "state", "tasks"));
    assert.equal(paths.eventsDir, join(root, ".sage-kit", "state", "events"));
    assert.equal(paths.runsDir, join(root, ".sage-kit", "state", "runs"));
    assert.equal(paths.briefPath, join(root, "SESSION_BRIEF.md"));

    assert.equal(await api.configExists(paths), false);
    assert.equal(await api.loadConfig(paths), null);

    const installedAt = new Date().toISOString();
    const config = {
      schemaVersion: 1,
      packageVersion: PACKAGE_VERSION,
      host: "fake",
      scope: "project",
      mode: "file",
      projectRoot: root,
      createdAt: installedAt,
      updatedAt: installedAt,
      skill: {
        path: join(root, ".fake", "skills", "sage-kit"),
        mode: "copy",
        files: ["SKILL.md"],
        installedAt,
      },
    };
    await mkdir(paths.stateDir, { recursive: true });
    await writeJson(paths.config, config);
    assert.equal(await api.configExists(paths), true);
    assert.deepEqual(await api.loadConfig(paths), config);

    await writeJson(paths.config, { ...config, scope: "workspace" });
    await assert.rejects(api.loadConfig(paths), sageError("E_BAD_CONFIG"));
    await writeJson(paths.config, { ...config, schemaVersion: 2 });
    await assert.rejects(api.loadConfig(paths), sageError("E_BAD_CONFIG"));
    await writeFile(paths.config, "{ not json");
    await assert.rejects(api.loadConfig(paths), sageError("E_BAD_JSON"));

    const project = await tempDir();
    await mkdir(join(project, ".git"));
    await mkdir(join(project, "nested", "deeper"), { recursive: true });
    assert.equal(await api.findProjectRoot(join(project, "nested", "deeper")), project);
    const plain = await tempDir();
    assert.equal(await api.findProjectRoot(join(plain, "sub")), resolve(join(plain, "sub")));

    assert.equal(api.homeDirectory({ HOME: "/home/example" }), "/home/example");
    assert.equal(api.homeDirectory({ USERPROFILE: "C:\\Users\\example" }), "C:\\Users\\example");
    assert.equal(api.homeDirectory({}), resolve("."));
  });

  it("API-6: CLI behavior is unchanged and interoperates with library-written state", async () => {
    const root = await tempDir();

    const version = await runCli(root, ["version"]);
    assert.equal(version.code, 0, version.stderr);
    assert.equal(version.stdout, `${PACKAGE_VERSION}\n`);

    const help = await runCli(root, ["--help"]);
    assert.equal(help.code, 0, help.stderr);
    assert.match(help.stdout, new RegExp(`^sage-kit ${PACKAGE_VERSION.replace(/\./g, "\\.")}`));
    assert.match(help.stdout, /sage-kit task create --title/);
    assert.match(help.stdout, /sage-kit task status <id> <status>/);

    const emptyList = await runCli(root, ["task", "list"]);
    assert.equal(emptyList.code, 0, emptyList.stderr);
    assert.equal(emptyList.stdout, "No tasks.\n");

    const created = await runCli(root, [
      "task",
      "create",
      "--title",
      "CLI text task",
      "--acceptance",
      "cli text mode works",
    ]);
    assert.equal(created.code, 0, created.stderr);
    assert.match(created.stdout, /^Created task-\d{14}-[0-9a-f]{6}: CLI text task\n$/);
    const id = created.stdout.trim().replace(/^Created ([^:]+): .*$/, "$1");

    const listJson = JSON.parse((await runCli(root, ["task", "list", "--json"])).stdout);
    assert.equal(listJson.ok, true);
    assert.equal(listJson.tasks.length, 1);
    assert.equal(listJson.tasks[0].id, id);
    assert.equal(listJson.tasks[0].status, "ready");
    assert.deepEqual(listJson.tasks[0].acceptance, ["cli text mode works"]);

    // The library reads CLI-written file-mode state...
    const paths = api.statePaths(root);
    assert.deepEqual(await api.readTask(paths, id), listJson.tasks[0]);

    // ...and the CLI reads library-written state.
    const fromLibrary = await api.createTask(paths, {
      id: "task-api-from-lib",
      title: "From library",
      acceptance: ["library path works"],
      status: "ready",
    });
    const listed = JSON.parse((await runCli(root, ["task", "list", "--json"])).stdout).tasks;
    assert.deepEqual(
      listed.map((task) => task.id).sort(),
      [id, "task-api-from-lib"].sort(),
    );
    const shown = JSON.parse((await runCli(root, ["task", "show", "task-api-from-lib", "--json"])).stdout);
    assert.deepEqual(shown.task, fromLibrary);

    const transition = await runCli(root, ["task", "status", id, "running", "--json"]);
    assert.equal(transition.code, 0, transition.stderr);
    assert.equal(JSON.parse(transition.stdout).task.status, "running");
    assert.equal((await api.readTask(paths, id)).status, "running");

    // CLI JSON error contract for a missing task is unchanged.
    const missing = await runCli(root, ["task", "show", "task-api-missing", "--json"]);
    assert.equal(missing.code, 1);
    const missingJson = JSON.parse(missing.stdout);
    assert.equal(missingJson.ok, false);
    assert.equal(missingJson.error.code, "E_TASK_NOT_FOUND");
  });
});
