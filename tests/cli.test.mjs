import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { git } from "../dist/core/process.js";

const CLI = fileURLToPath(new URL("../dist/cli.js", import.meta.url));
const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const cleanups = [];
await mkdir(TEST_TMP_BASE, { recursive: true });

function runCli(cwd, args, stdin = "") {
  return new Promise((resolvePromise) => {
    const child = spawn(process.execPath, [CLI, ...args], {
      cwd,
      env: { ...process.env, NO_COLOR: "1" },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => resolvePromise({ code, stdout, stderr }));
    child.stdin.end(stdin);
  });
}

async function tempDir() {
  const dir = await mkdtemp(join(TEST_TMP_BASE, "sage-kit-"));
  cleanups.push(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

async function initFake(cwd) {
  const result = await runCli(cwd, ["init", "--host", "fake", "--scope", "project", "--no-instructions"]);
  assert.equal(result.code, 0, result.stderr);
}

async function createTask(cwd, title = "Test task") {
  const result = await runCli(cwd, ["task", "create", "--title", title, "--acceptance", "checks pass"]);
  assert.equal(result.code, 0, result.stderr);
  const list = await runCli(cwd, ["task", "list", "--json"]);
  return JSON.parse(list.stdout).tasks[0].id;
}

after(async () => {
  for (const cleanup of cleanups.reverse()) await cleanup().catch(() => {});
});

describe("P0 CLI", () => {
  it("A1: prints help and version", async () => {
    const cwd = await tempDir();
    const help = await runCli(cwd, ["--help"]);
    assert.equal(help.code, 0);
    assert.match(help.stdout, /sage-kit init/);
    const version = await runCli(cwd, ["version"]);
    assert.equal(version.code, 0);
    assert.match(version.stdout, /^0\.1\.0/);
  });

  it("A2/A3: initializes idempotently and uninstalls without touching user files", async () => {
    const cwd = await tempDir();
    await writeFile(join(cwd, "AGENTS.md"), "# User instructions\n\nKeep me.\n", "utf8");
    await initFake(cwd);
    const config = JSON.parse(await readFile(join(cwd, ".sage-kit", "config.json"), "utf8"));
    assert.equal(config.host, "fake");
    assert.match(await readFile(join(cwd, ".fake", "skills", "sage-kit", "SKILL.md"), "utf8"), /name: sage-kit/);
    assert.match(await readFile(join(cwd, "SESSION_BRIEF.md"), "utf8"), /SAGE-Kit brief/);

    const second = await runCli(cwd, ["init", "--host", "fake", "--scope", "project", "--no-instructions"]);
    assert.equal(second.code, 0, second.stderr);

    const uninstall = await runCli(cwd, ["uninstall"]);
    assert.equal(uninstall.code, 0, uninstall.stderr);
    assert.equal(await readFile(join(cwd, "AGENTS.md"), "utf8"), "# User instructions\n\nKeep me.\n");
    await assert.rejects(readFile(join(cwd, ".sage-kit", "config.json")));
  });

  it("A2b: installs file adapters for Codex and Claude", async () => {
    for (const host of ["codex", "claude"]) {
      const cwd = await tempDir();
      const result = await runCli(cwd, ["init", "--host", host, "--scope", "project"]);
      assert.equal(result.code, 0, result.stderr);
      const skill =
        host === "codex"
          ? join(cwd, ".agents", "skills", "sage-kit", "SKILL.md")
          : join(cwd, ".claude", "skills", "sage-kit", "SKILL.md");
      assert.match(await readFile(skill, "utf8"), /name: sage-kit/);
      const instructions = host === "codex" ? join(cwd, "AGENTS.md") : join(cwd, "CLAUDE.md");
      assert.match(await readFile(instructions, "utf8"), /SAGE-Kit/);
      assert.equal((await runCli(cwd, ["uninstall"])).code, 0);
    }
  });

  it("A4: doctor reports healthy state and rejects corrupt config", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const healthy = await runCli(cwd, ["doctor", "--json"]);
    assert.equal(healthy.code, 0, healthy.stderr);
    assert.equal(JSON.parse(healthy.stdout).ok, true);

    await writeFile(join(cwd, ".sage-kit", "config.json"), "{ broken", "utf8");
    const broken = await runCli(cwd, ["doctor", "--json"]);
    assert.notEqual(broken.code, 0);
    assert.equal(JSON.parse(broken.stdout).ok, false);
  });

  it("A5: enforces lifecycle, evidence and task files", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd);

    assert.equal((await runCli(cwd, ["task", "status", id, "running"])).code, 0);
    assert.equal((await runCli(cwd, ["task", "status", id, "review"])).code, 0);
    const withoutEvidence = await runCli(cwd, ["task", "status", id, "done"]);
    assert.notEqual(withoutEvidence.code, 0);
    const done = await runCli(cwd, ["task", "status", id, "done", "--evidence", "tests/cli.test.mjs"]);
    assert.equal(done.code, 0, done.stderr);

    const task = JSON.parse(await readFile(join(cwd, ".sage-kit", "state", "tasks", `${id}.json`), "utf8"));
    assert.equal(task.status, "done");
    assert.equal(task.evidence.at(-1).note, "tests/cli.test.mjs");

    const list = await runCli(cwd, ["task", "list", "--json"]);
    const listed = JSON.parse(list.stdout).tasks.find((item) => item.id === id);
    assert.equal(listed.status, "done");
  });

  it("A7: brief contains task acceptance and respects the byte budget", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd, "Brief task");
    const brief = await runCli(cwd, ["brief", "--task", id, "--max-bytes", "256", "--json"]);
    assert.equal(brief.code, 0, brief.stderr);
    const parsed = JSON.parse(brief.stdout);
    assert.equal(parsed.taskId, id);
    assert.match(parsed.text, /Brief task/);
    assert.ok(Buffer.byteLength(parsed.text) <= 256);
  });

  it("A8/A9/A10: hook contracts, command.after redaction and stop strictness", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd, "Hook task");

    const start = await runCli(
      cwd,
      ["hook", "--event", "session.start"],
      JSON.stringify({ contractVersion: "1", event: "session.start", cwd, taskId: id }),
    );
    assert.equal(start.code, 0, start.stderr);
    const startJson = JSON.parse(start.stdout);
    assert.equal(startJson.action, "inject_context");
    assert.match(startJson.context, /Hook task/);

    const after = await runCli(
      cwd,
      ["hook", "--event", "command.after"],
      JSON.stringify({
        contractVersion: "1",
        event: "command.after",
        cwd,
        taskId: id,
        payload: {
          command: {
            argv: ["node", "-e", "exit"],
            exitCode: 0,
            durationMs: 12,
            stdoutTail: "token=secret-value",
          },
        },
      }),
    );
    assert.equal(after.code, 0, after.stderr);
    assert.equal(JSON.parse(after.stdout).action, "noop");
    const events = await readFile(join(cwd, ".sage-kit", "state", "events", "events.jsonl"), "utf8");
    assert.doesNotMatch(events, /secret-value/);

    const stop = await runCli(
      cwd,
      ["hook", "--event", "stop", "--strict"],
      JSON.stringify({ contractVersion: "1", event: "stop", cwd, taskId: id }),
    );
    assert.notEqual(stop.code, 0);
    assert.equal(JSON.parse(stop.stdout).action, "block");

    const bad = await runCli(cwd, ["hook", "--event", "session.start"], "{not-json");
    assert.equal(bad.code, 2, bad.stderr);
    assert.equal(JSON.parse(bad.stdout).action, "warn");
  });

  it("A6: creates and removes isolated worktrees; refuses dirty removal", async () => {
    const cwd = await tempDir();
    assert.equal((await git(cwd, ["init", "-q"])).code, 0);
    await git(cwd, ["config", "user.email", "test@example.com"]);
    await git(cwd, ["config", "user.name", "tester"]);
    await writeFile(join(cwd, "README.md"), "hello\n", "utf8");
    await git(cwd, ["add", "README.md"]);
    await git(cwd, ["commit", "-qm", "initial"]);
    await initFake(cwd);
    const id = await createTask(cwd, "Worktree task");

    const created = await runCli(cwd, ["worktree", "create", "--task", id, "--json"]);
    assert.equal(created.code, 0, created.stderr);
    const worktree = JSON.parse(created.stdout).task.worktree;
    assert.match(worktree, /\.sage-kit[\\/]worktrees/);
    await writeFile(join(worktree, "dirty.txt"), "dirty\n", "utf8");

    assert.notEqual((await runCli(cwd, ["worktree", "remove", "--task", id])).code, 0);
    assert.equal((await runCli(cwd, ["worktree", "remove", "--task", id, "--force"])).code, 0);
  });

  it("A11: recovers a stale running run as interrupted", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd, "Crash task");
    await runCli(cwd, ["task", "status", id, "running"]);
    const runsDir = join(cwd, ".sage-kit", "state", "runs");
    await mkdir(runsDir, { recursive: true });
    await writeFile(
      join(runsDir, "run-stale.json"),
      JSON.stringify({
        schemaVersion: 1,
        id: "run-stale",
        taskId: id,
        command: ["fake"],
        cwd,
        status: "running",
        pid: 999999,
        startedAt: new Date(0).toISOString(),
      }),
      "utf8",
    );
    const doctor = await runCli(cwd, ["doctor", "--json"]);
    assert.equal(doctor.code, 0, doctor.stderr);
    const task = JSON.parse(await readFile(join(cwd, ".sage-kit", "state", "tasks", `${id}.json`), "utf8"));
    assert.equal(task.status, "interrupted");
    const run = JSON.parse(await readFile(join(runsDir, "run-stale.json"), "utf8"));
    assert.equal(run.status, "interrupted");
  });

  it("A12: rejects path traversal and runs a command in the project", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const traversal = await runCli(cwd, ["task", "create", "--title", "bad", "--id", "../../escape"]);
    assert.notEqual(traversal.code, 0);

    const id = await createTask(cwd);
    const run = await runCli(cwd, ["run", "--task", id, "--no-worktree", "--", "node", "-e", "console.log('ok')"]);
    assert.equal(run.code, 0, run.stderr);
    const task = JSON.parse(await readFile(join(cwd, ".sage-kit", "state", "tasks", `${id}.json`), "utf8"));
    assert.equal(task.status, "review");
    const events = await readFile(join(cwd, ".sage-kit", "state", "events", "events.jsonl"), "utf8");
    assert.ok(events.includes("run.started"));

    const injected = join(cwd, "injected-by-shell");
    const metachar = await runCli(cwd, [
      "run",
      "--task",
      id,
      "--no-worktree",
      "--",
      "node",
      "-e",
      "console.log(process.argv[1])",
      `; touch ${injected}`,
    ]);
    assert.equal(metachar.code, 0, metachar.stderr);
    await assert.rejects(readFile(injected));
  });
});
