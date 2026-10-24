import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { lstat, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { checkNode } from "../dist/core/doctor.js";
import { truncateUtf8 } from "../dist/core/fs-utils.js";
import { git } from "../dist/core/process.js";

const CLI = fileURLToPath(new URL("../dist/cli.js", import.meta.url));
const REPO_ROOT = fileURLToPath(new URL("..", import.meta.url));
const PACKAGE_VERSION = JSON.parse(await readFile(join(REPO_ROOT, "package.json"), "utf8")).version;
const NPM = process.platform === "win32" ? "npm.cmd" : "npm";
const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const cleanups = [];
await mkdir(TEST_TMP_BASE, { recursive: true });

function runProcess(command, args, cwd, options = {}) {
  const timeoutMs = options.timeoutMs ?? 60_000;
  return new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, NO_COLOR: "1", ...(options.env ?? {}) },
      stdio: ["pipe", "pipe", "pipe"],
      shell: Boolean(options.shell),
    });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, timeoutMs);
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolvePromise({ code, stdout, stderr, timedOut });
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.stdin.end(options.stdin ?? "");
  });
}

function runCli(cwd, args, stdin = "", extraEnv = {}) {
  return runProcess(process.execPath, [CLI, ...args], cwd, { stdin, env: extraEnv });
}

function sleep(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

async function waitFor(probe, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = await probe();
    if (value) return value;
    if (Date.now() >= deadline) throw new Error(`Timed out after ${timeoutMs}ms waiting for ${label}`);
    await sleep(25);
  }
}

function isAlivePid(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
}

// POSIX: execute the installed `node_modules/.bin/sage-kit` shim so the `bin`
// field and executable bit are exercised. win32: fall back to the installed
// cli.js (Windows is not a test target; the .cmd shim needs a shell).
function runInstalled(cwd, args) {
  if (process.platform === "win32") {
    return runProcess(process.execPath, [join(cwd, "node_modules", "sage-kit", "dist", "cli.js"), ...args], cwd);
  }
  return runProcess(join(cwd, "node_modules", ".bin", "sage-kit"), args, cwd);
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
    // Version must come from package.json, not a hardcoded constant.
    assert.match(help.stdout, new RegExp(`^sage-kit ${PACKAGE_VERSION.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`, "m"));
    const version = await runCli(cwd, ["version"]);
    assert.equal(version.code, 0);
    assert.equal(version.stdout.trim(), PACKAGE_VERSION);
  });

  it("A1b: packs and installs a runtime-dependency-free CLI offline", async () => {
    const packDir = await tempDir();
    const installDir = await tempDir();
    // `npm test` already built dist; ignore prepack to avoid rewriting dist while
    // sibling test files import it concurrently (CI Linux caught this race).
    const pack = await runProcess(
      NPM,
      ["pack", "--json", "--ignore-scripts", "--pack-destination", packDir],
      REPO_ROOT,
      { shell: process.platform === "win32" },
    );
    assert.equal(pack.code, 0, pack.stderr);
    const [packInfo] = JSON.parse(pack.stdout);
    assert.equal(packInfo.name, "sage-kit");
    assert.equal(packInfo.version, PACKAGE_VERSION);
    const packed = packInfo.files.map((file) => file.path);
    for (const required of ["dist/cli.js", "skills/sage-kit/SKILL.md", "package.json"]) {
      assert.ok(packed.includes(required), `tarball is missing ${required}`);
    }
    const forbidden = [/^tests\//, /^reports\//, /^work\//, /^src\//, /^node_modules\//, /^\.git\//, /^\.sage-kit\//, /^scripts\//];
    const leaked = packed.filter((path) => forbidden.some((pattern) => pattern.test(path)));
    assert.deepEqual(leaked, [], `tarball contains non-shipped paths: ${leaked.join(", ")}`);

    await writeFile(
      join(installDir, "package.json"),
      `${JSON.stringify({ name: "sage-kit-install-smoke", version: "1.0.0", private: true }, null, 2)}\n`,
      "utf8",
    );
    const install = await runProcess(
      NPM,
      ["install", "--no-audit", "--no-fund", "--ignore-scripts", "--offline", join(packDir, packInfo.filename)],
      installDir,
      {
        shell: process.platform === "win32",
        // Isolated empty cache: proves the install needs neither the network nor
        // any pre-populated npm cache (the package has no runtime dependencies).
        env: { npm_config_cache: join(installDir, ".npm-cache") },
      },
    );
    assert.equal(install.code, 0, install.stderr);
    const installed = JSON.parse(await readFile(join(installDir, "node_modules", "sage-kit", "package.json"), "utf8"));
    assert.equal(installed.name, "sage-kit");
    assert.equal(installed.version, PACKAGE_VERSION);
    assert.equal(installed.dependencies, undefined, "P0 package must not have runtime dependencies");

    const version = await runInstalled(installDir, ["version"]);
    assert.equal(version.code, 0, version.stderr);
    assert.equal(version.stdout.trim(), installed.version);

    const uninitialized = await runInstalled(installDir, ["doctor", "--json"]);
    assert.notEqual(uninitialized.code, 0);
    const uninitializedJson = JSON.parse(uninitialized.stdout);
    assert.equal(uninitializedJson.ok, false);
    assert.equal(uninitializedJson.checks.find((check) => check.name === "config").status, "error");

    const init = await runInstalled(installDir, ["init", "--host", "fake", "--scope", "project", "--no-instructions"]);
    assert.equal(init.code, 0, init.stderr);
    assert.match(await readFile(join(installDir, ".fake", "skills", "sage-kit", "SKILL.md"), "utf8"), /name: sage-kit/);

    const healthy = await runInstalled(installDir, ["doctor", "--json"]);
    assert.equal(healthy.code, 0, healthy.stderr);
    const healthyJson = JSON.parse(healthy.stdout);
    assert.equal(healthyJson.ok, true);
    assert.equal(healthyJson.projectRoot, installDir);
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

  it("A2c: records the actual existing skill mode on re-init", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    // Requested symlink is ignored because the existing copy is kept; config
    // must record what is actually installed (copy), not the requested mode.
    const kept = await runCli(cwd, [
      "init",
      "--host",
      "fake",
      "--scope",
      "project",
      "--mode",
      "symlink",
      "--no-instructions",
    ]);
    assert.equal(kept.code, 0, kept.stderr);
    assert.match(kept.stdout, /kept it/);
    let config = JSON.parse(await readFile(join(cwd, ".sage-kit", "config.json"), "utf8"));
    assert.equal(config.skill.mode, "copy");

    if (process.platform !== "win32") {
      const symlinkCwd = await tempDir();
      const created = await runCli(symlinkCwd, [
        "init",
        "--host",
        "fake",
        "--scope",
        "project",
        "--mode",
        "symlink",
        "--no-instructions",
      ]);
      assert.equal(created.code, 0, created.stderr);
      config = JSON.parse(await readFile(join(symlinkCwd, ".sage-kit", "config.json"), "utf8"));
      assert.equal(config.skill.mode, "symlink");
      assert.equal((await lstat(config.skill.path)).isSymbolicLink(), true);

      // Re-init requesting copy keeps the symlink and records the actual mode.
      const keptSymlink = await runCli(symlinkCwd, [
        "init",
        "--host",
        "fake",
        "--scope",
        "project",
        "--mode",
        "copy",
        "--no-instructions",
      ]);
      assert.equal(keptSymlink.code, 0, keptSymlink.stderr);
      config = JSON.parse(await readFile(join(symlinkCwd, ".sage-kit", "config.json"), "utf8"));
      assert.equal(config.skill.mode, "symlink");
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

  it("A4b: doctor fails with a skill error when the installed skill is missing", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    await rm(join(cwd, ".fake", "skills", "sage-kit"), { recursive: true, force: true });

    const doctor = await runCli(cwd, ["doctor", "--json"]);
    assert.notEqual(doctor.code, 0);
    const parsed = JSON.parse(doctor.stdout);
    assert.equal(parsed.ok, false);
    const skillCheck = parsed.checks.find((check) => check.name === "skill");
    assert.equal(skillCheck.status, "error");
    assert.match(skillCheck.detail, /missing/);

    const text = await runCli(cwd, ["doctor"]);
    assert.notEqual(text.code, 0);
    assert.match(text.stdout, /SAGE-Kit doctor: FAILED/);
    assert.match(text.stdout, /\[error\] skill: missing/);
  });

  it("A4c: doctor resolves HOME for global-scope installs", async () => {
    const hosts = { fake: ".fake-global", codex: ".agents", claude: ".claude" };
    for (const [host, folder] of Object.entries(hosts)) {
      const home = await tempDir();
      const cwd = await tempDir();
      const env = { HOME: home, USERPROFILE: home };
      const init = await runCli(
        cwd,
        ["init", "--host", host, "--scope", "global", "--no-instructions"],
        "",
        env,
      );
      assert.equal(init.code, 0, init.stderr);
      const config = JSON.parse(await readFile(join(cwd, ".sage-kit", "config.json"), "utf8"));
      assert.equal(config.scope, "global");
      const expectedSkill = join(home, folder, "skills", "sage-kit");
      assert.equal(config.skill.path, expectedSkill);
      assert.match(await readFile(join(expectedSkill, "SKILL.md"), "utf8"), /name: sage-kit/);

      const doctor = await runCli(cwd, ["doctor", "--json"], "", env);
      assert.equal(doctor.code, 0, doctor.stderr);
      const parsed = JSON.parse(doctor.stdout);
      assert.equal(parsed.ok, true);
      assert.equal(
        parsed.checks.some((check) => check.name === "skill-path"),
        false,
        `${host}: unexpected skill-path warning`,
      );
      const skillCheck = parsed.checks.find((check) => check.name === "skill");
      assert.equal(skillCheck.status, "ok");
      assert.ok(skillCheck.detail.startsWith(expectedSkill), skillCheck.detail);
      assert.ok(parsed.checks.find((check) => check.name === "skill-duplicates").detail.includes(expectedSkill));

      // A different HOME must still be flagged: the check is not blanket-disabled.
      const otherHome = await tempDir();
      const mismatched = await runCli(cwd, ["doctor", "--json"], "", { HOME: otherHome, USERPROFILE: otherHome });
      assert.equal(mismatched.code, 0, mismatched.stderr);
      const mismatchedJson = JSON.parse(mismatched.stdout);
      assert.equal(mismatchedJson.ok, true);
      assert.equal(mismatchedJson.checks.find((check) => check.name === "skill-path").status, "warn");
    }
  });

  it("A4d: Node floor is a single >=22 policy", async () => {
    for (const version of ["20.11.0", "21.9.0"]) {
      const check = checkNode(version);
      assert.equal(check.status, "error", version);
      assert.match(check.detail, /need >=22/);
    }
    for (const version of ["22.0.0", "22.19.9", "24.0.0"]) {
      assert.equal(checkNode(version).status, "ok", version);
    }
    const cwd = await tempDir();
    await initFake(cwd);
    const doctor = JSON.parse((await runCli(cwd, ["doctor", "--json"])).stdout);
    assert.equal(doctor.checks.find((check) => check.name === "node").status, "ok");
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

  it("A7b: truncates non-ASCII briefs on code-point boundaries", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd, "验收😀".repeat(40));
    const brief = await runCli(cwd, ["brief", "--task", id, "--max-bytes", "256", "--json"]);
    assert.equal(brief.code, 0, brief.stderr);
    const parsed = JSON.parse(brief.stdout);
    assert.equal(parsed.truncated, true);
    const bytes = Buffer.byteLength(parsed.text, "utf8");
    assert.ok(bytes <= 256, `brief is ${bytes} bytes`);
    assert.ok(!parsed.text.includes("\uFFFD"), "brief contains U+FFFD replacement characters");
    assert.ok(parsed.text.endsWith("…[truncated]"));

    // Direct boundary fuzz across 2-, 3- and 4-byte code points.
    for (const sample of ["😀".repeat(30), "验收测试".repeat(20), "é".repeat(40), "x😀y"]) {
      for (let maxBytes = 1; maxBytes <= 60; maxBytes += 1) {
        const { text } = truncateUtf8(sample, maxBytes);
        assert.ok(Buffer.byteLength(text, "utf8") <= maxBytes, `sample=${JSON.stringify(sample)} max=${maxBytes}`);
        assert.ok(!text.includes("\uFFFD"), `sample=${JSON.stringify(sample)} max=${maxBytes}`);
      }
    }
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

    const unknown = await runCli(
      cwd,
      ["hook", "--event", "unknown.event"],
      JSON.stringify({ contractVersion: "1", event: "unknown.event", cwd }),
    );
    assert.equal(unknown.code, 2, unknown.stderr);
    assert.equal(JSON.parse(unknown.stdout).action, "warn");
  });

  it("A8b: hook --timeout bounds a stalled stdin and exits 124 with valid JSON", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const startedAt = Date.now();
    const child = spawn(process.execPath, [CLI, "hook", "--event", "session.start", "--timeout", "120"], {
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
    child.stdin.on("error", () => {});
    // stdin is deliberately left open and silent: the hook must self-terminate.
    const result = await Promise.race([
      new Promise((resolveClose) => child.on("close", (code, signal) => resolveClose({ code, signal }))),
      sleep(10_000).then(() => {
        child.kill("SIGKILL");
        return { code: null, signal: "TEST_TIMEOUT" };
      }),
    ]);
    const elapsedMs = Date.now() - startedAt;
    child.stdin.destroy();
    assert.equal(result.signal, null, stderr);
    assert.equal(result.code, 124, stderr);
    assert.ok(elapsedMs >= 100 && elapsedMs < 10_000, `unexpected elapsed ${elapsedMs}ms`);
    const parsed = JSON.parse(stdout);
    assert.equal(parsed.contractVersion, "1");
    assert.equal(parsed.action, "warn");
    assert.equal(parsed.code, "E_HOOK_TIMEOUT");
    assert.match(parsed.message, /120ms/);
    // Timeout is fail-open and side-effect free: no hook event is recorded.
    await assert.rejects(readFile(join(cwd, ".sage-kit", "state", "events", "events.jsonl")));
  });

  it("A8c: hook rejects invalid --timeout values as contract usage errors", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const input = JSON.stringify({ contractVersion: "1", event: "session.start", cwd });
    for (const value of ["abc", "10", "2001", "1.5", "NaN"]) {
      const result = await runCli(cwd, ["hook", "--event", "session.start", "--timeout", value], input);
      assert.equal(result.code, 2, `${value}: ${result.stderr}`);
      const parsed = JSON.parse(result.stdout);
      assert.equal(parsed.ok, false);
      assert.equal(parsed.error.code, "E_USAGE");
      assert.match(parsed.error.message, /--timeout/);
    }
    const min = await runCli(cwd, ["hook", "--event", "session.start", "--timeout", "50"], input);
    assert.equal(min.code, 0, min.stderr);
    assert.equal(JSON.parse(min.stdout).action, "warn");
    const max = await runCli(cwd, ["hook", "--event", "session.start", "--timeout", "2000"], input);
    assert.equal(max.code, 0, max.stderr);
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

  it("A11b: recovers a task and run after a real SIGKILL of the launching CLI", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd, "Killed run task");
    const runsDir = join(cwd, ".sage-kit", "state", "runs");
    const marker = join(cwd, "run-exit-marker");
    // The wrapped command stays alive until the marker exists, then exits on its
    // own. This removes any timing race between "run record written" and "CLI
    // killed" while still leaving a normal child exit to be reaped.
    const wrapped = [
      "const fs = require('node:fs');",
      "const marker = process.argv[1];",
      "const timer = setInterval(() => { if (fs.existsSync(marker)) { clearInterval(timer); process.exit(0); } }, 25);",
      "setTimeout(() => process.exit(2), 15000);",
    ].join(" ");
    const child = spawn(
      process.execPath,
      [CLI, "run", "--task", id, "--no-worktree", "--", process.execPath, "-e", wrapped, marker],
      { cwd, env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] },
    );
    const closed = new Promise((resolveClose) => child.on("close", resolveClose));
    const exited = new Promise((resolveExit) => child.on("exit", resolveExit));
    try {
      const runFile = await waitFor(
        async () => {
          const names = await readdir(runsDir).catch(() => []);
          const name = names.find((entry) => entry.endsWith(".json"));
          return name ? join(runsDir, name) : null;
        },
        15_000,
        "run record",
      );
      const startedRun = JSON.parse(await readFile(runFile, "utf8"));
      assert.equal(startedRun.status, "running");
      assert.ok(Number.isInteger(startedRun.pid) && startedRun.pid > 0);

      assert.equal(child.kill("SIGKILL"), true);
      // `exit` (not `close`) fires once the CLI itself is gone; `close` also
      // waits for the wrapped command, which inherits the CLI's stdio pipes.
      await exited;
      await writeFile(marker, "exit\n", "utf8");
      await waitFor(() => !isAlivePid(startedRun.pid), 15_000, "run child to exit and be reaped");
      await closed;

      const doctor = await runCli(cwd, ["doctor", "--json"]);
      assert.equal(doctor.code, 0, doctor.stderr);
      const parsed = JSON.parse(doctor.stdout);
      assert.equal(parsed.ok, true);
      assert.equal(parsed.checks.find((check) => check.name === "runs").status, "warn");
      assert.equal(JSON.parse(await readFile(runFile, "utf8")).status, "interrupted");
      const task = JSON.parse(await readFile(join(cwd, ".sage-kit", "state", "tasks", `${id}.json`), "utf8"));
      assert.equal(task.status, "interrupted");
      const list = JSON.parse((await runCli(cwd, ["task", "list", "--json"])).stdout);
      assert.equal(list.tasks.find((item) => item.id === id).status, "interrupted");
    } finally {
      if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
    }
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

describe("M1/M2/M3 CLI integration", () => {
  it("feedback list returns an empty untrusted payload in a fresh repo", async () => {
    const cwd = await tempDir();
    const result = await runCli(cwd, ["feedback", "list", "--json"]);
    assert.equal(result.code, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.ok, true);
    assert.equal(payload.untrustedData, true);
    assert.equal(payload.count, 0);
  });

  it("control status opens the SQLite foundation without changing file-mode tasks", async () => {
    const cwd = await tempDir();
    await initFake(cwd);
    const id = await createTask(cwd, "Control bridge task");
    const result = await runCli(cwd, ["control", "status", "--json"]);
    assert.equal(result.code, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.ok, true);
    assert.equal(payload.counts.tasks, 0);
    const fileTask = JSON.parse(await readFile(join(cwd, ".sage-kit", "state", "tasks", `${id}.json`), "utf8"));
    assert.equal(fileTask.status, "ready");
    assert.equal(fileTask.title, "Control bridge task");
  });

  it("rsi list is available and empty in a fresh repo", async () => {
    const cwd = await tempDir();
    const result = await runCli(cwd, ["rsi", "list", "--json"]);
    assert.equal(result.code, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.ok, true);
    assert.deepEqual(payload.proposals, []);
  });

  it("control serve binds loopback and serves UI/API without a token", async () => {
    const cwd = await tempDir();
    const child = spawn(process.execPath, [CLI, "control", "serve", "--port", "0", "--json"], {
      cwd,
      stdio: ["ignore", "pipe", "pipe"],
    });
    try {
      let stdout = "";
      const line = await new Promise((resolvePromise, rejectPromise) => {
        const timer = setTimeout(() => rejectPromise(new Error(`control serve did not print a URL: ${stdout}`)), 10_000);
        child.stdout.on("data", (chunk) => {
          stdout += chunk.toString();
          const newline = stdout.indexOf("\n");
          if (newline >= 0) {
            clearTimeout(timer);
            resolvePromise(stdout.slice(0, newline));
          }
        });
        child.once("exit", (code) => {
          clearTimeout(timer);
          rejectPromise(new Error(`control serve exited early with ${code}: ${stdout}`));
        });
      });
      const started = JSON.parse(line);
      assert.equal(started.ok, true);
      assert.match(started.url, /^http:\/\/127\.0\.0\.1:\d+$/);
      const health = await fetch(`${started.url}/v1/health`);
      assert.equal(health.status, 200);
      assert.match(started.uiUrl, /\/ui$/);
      const ui = await fetch(`${started.url}/ui`);
      assert.equal(ui.status, 200);
    } finally {
      if (child.exitCode === null && child.signalCode === null) child.kill("SIGTERM");
      await new Promise((resolvePromise) => {
        if (child.exitCode !== null || child.signalCode !== null) resolvePromise(undefined);
        else child.once("exit", () => resolvePromise(undefined));
      });
    }
  });
});
