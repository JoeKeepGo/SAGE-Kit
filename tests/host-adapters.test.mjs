import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import {
  CodexAdapter,
  codexHostBundleRoot,
  installCodexHostBundle,
  uninstallCodexHostBundle,
} from "../dist/adapters/codex.js";
import {
  ClaudeAdapter,
  installClaudeHostBundle,
  uninstallClaudeHostBundle,
} from "../dist/adapters/claude.js";
import { SageError } from "../dist/core/errors.js";
import { installHostBundle, uninstallHostBundle } from "../dist/adapters/host-bundle.js";

const REPO_ROOT = fileURLToPath(new URL("..", import.meta.url));
const CLI = join(REPO_ROOT, "dist", "cli.js");
const PACKAGE_VERSION = JSON.parse(await readFile(join(REPO_ROOT, "package.json"), "utf8")).version;
const CODEX_PACKAGE = join(REPO_ROOT, "packages", "host-codex");
const CLAUDE_PACKAGE = join(REPO_ROOT, "packages", "host-claude");
const CANONICAL_SKILL = join(REPO_ROOT, "skills", "sage-kit", "SKILL.md");
const TMP_BASE = process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const CODEX_BIN = process.env.SAGE_KIT_CODEX_BIN ?? "codex";
const codexProbe = spawnSync(CODEX_BIN, ["--version"], { encoding: "utf8", timeout: 10_000 });
const CODEX_AVAILABLE = !codexProbe.error && codexProbe.status === 0;

await mkdir(TMP_BASE, { recursive: true });
const cleanups = [];
after(async () => {
  for (const dir of cleanups) await rm(dir, { recursive: true, force: true });
});

async function tempDir(label) {
  const dir = await mkdtemp(join(TMP_BASE, `host-${label}-`));
  cleanups.push(dir);
  return dir;
}

function runProcess(command, args, options = {}) {
  const timeoutMs = options.timeoutMs ?? 60_000;
  return new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd ?? REPO_ROOT,
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
    if (options.stdin !== undefined) child.stdin.end(options.stdin);
    else child.stdin.end();
  });
}

function runBridge(packageDir, options = {}) {
  return runProcess(process.execPath, [join(packageDir, "hooks", "session-start.cjs")], {
    cwd: options.cwd ?? REPO_ROOT,
    stdin: options.stdin ?? "",
    env: options.env ?? {},
    timeoutMs: options.timeoutMs ?? 15_000,
  });
}

async function writeFakeCli(dir) {
  const file = join(dir, "fake-cli.js");
  const lines = [
    '"use strict";',
    'const { writeFileSync } = require("node:fs");',
    'const mode = process.env.FAKE_MODE || "ok";',
    'if (mode === "touch") { if (process.env.FAKE_TOUCH) writeFileSync(process.env.FAKE_TOUCH, "ran"); }',
    'if (mode === "sleep") { setInterval(() => {}, 1000); }',
    'if (mode === "malformed") { process.stdout.write("not-json"); }',
    'if (mode === "fail") { process.stdout.write("nope"); process.exit(1); }',
    'if (mode === "echo-cwd") { process.stdout.write(JSON.stringify({ text: "# SAGE-Kit brief\\n\\ncwd=" + process.cwd(), truncated: false })); }',
    "if (mode === \"ok\" || mode === \"touch\") {",
    '  const bytes = Number(process.env.FAKE_BYTES || 0);',
    '  process.stdout.write(JSON.stringify({ text: "# SAGE-Kit brief\\n\\n" + "x".repeat(bytes), truncated: bytes > 0 }));',
    "}",
    "",
  ];
  await writeFile(file, lines.join("\n"), "utf8");
  return file;
}

async function initFakeProject(dir, options = {}) {
  const project = join(dir, "project");
  await mkdir(join(project, ".sage-kit"), { recursive: true });
  await writeFile(
    join(project, ".sage-kit", "config.json"),
    `${JSON.stringify({ schemaVersion: 1, host: "codex", scope: "project", mode: "file" }, null, 2)}\n`,
    "utf8",
  );
  if (options.withGit) {
    await mkdir(project, { recursive: true });
    const result = await runProcess("git", ["init", "-q", "."], { cwd: project });
    assert.equal(result.code, 0);
  }
  return project;
}

function hookPayload(cwd) {
  return JSON.stringify({ session_id: "test-session", cwd, hook_event_name: "SessionStart", source: "startup" });
}

function parseBridgeJson(stdout) {
  return JSON.parse(stdout.trim());
}

describe("host package templates", () => {
  it("codex manifest/hook templates parse and keep version injection out of the template", async () => {
    const manifestRaw = await readFile(join(CODEX_PACKAGE, ".codex-plugin", "plugin.json"), "utf8");
    const manifest = JSON.parse(manifestRaw);
    assert.equal(manifest.name, "sage-kit");
    assert.equal(manifest.skills, "./skills/");
    assert.equal(manifest.hooks, "./hooks/hooks.json");
    assert.equal(manifest.version, undefined);
    const hooks = JSON.parse(await readFile(join(CODEX_PACKAGE, "hooks", "hooks.json"), "utf8"));
    const handler = hooks.hooks.SessionStart[0].hooks[0];
    assert.equal(handler.type, "command");
    assert.match(handler.command, /session-start\.cjs/);
    assert.match(handler.command, /CLAUDE_PLUGIN_ROOT/);
    assert.ok(!handler.command.includes("${"), "hook command must not depend on shell-specific ${VAR} expansion");
    assert.ok(handler.timeout >= 1);
  });

  it("claude manifest/hook templates parse and share the codex bridge", async () => {
    const manifest = JSON.parse(await readFile(join(CLAUDE_PACKAGE, ".claude-plugin", "plugin.json"), "utf8"));
    assert.equal(manifest.name, "sage-kit");
    assert.deepEqual(manifest.hooks, ["./hooks/hooks.json"]);
    assert.equal(manifest.version, undefined);
    const codexBridge = await readFile(join(CODEX_PACKAGE, "hooks", "session-start.cjs"));
    const claudeBridge = await readFile(join(CLAUDE_PACKAGE, "hooks", "session-start.cjs"));
    assert.ok(codexBridge.equals(claudeBridge), "codex and claude bridges must stay byte-identical");
    const codexHooks = await readFile(join(CODEX_PACKAGE, "hooks", "hooks.json"), "utf8");
    const claudeHooks = await readFile(join(CLAUDE_PACKAGE, "hooks", "hooks.json"), "utf8");
    assert.equal(codexHooks, claudeHooks);
  });

  it("does not claim host hook activation in adapter capabilities", () => {
    for (const adapter of [new CodexAdapter(), new ClaudeAdapter()]) {
      assert.deepEqual(adapter.capabilities.hooks, []);
      assert.equal(adapter.mapHook("session.start"), null);
    }
  });
});

describe("codex host bundle", () => {
  it("N05: failed installation never owns an uncreated destination later filled by the user", async () => {
    const dir = await tempDir("pending-ownership");
    const pluginSource = join(dir, "template");
    const skillSource = join(dir, "skill");
    await mkdir(pluginSource);
    await mkdir(skillSource);
    await writeFile(join(pluginSource, "a.txt"), "installed\n");
    await writeFile(join(pluginSource, "z-manifest.json"), "invalid JSON");
    await writeFile(join(skillSource, "SKILL.md"), "# managed skill\n");
    const spec = {
      host: "codex", bundleRoot: join(dir, ".sage-kit", "hosts", "codex"),
      pluginName: "sage-kit", pluginSource, pluginManifestPath: "z-manifest.json",
      marketplacePath: "marketplace.json", marketplace: { name: "sage-kit" },
      skillSource, skillRelativePath: "skills/sage-kit", version: "test",
    };
    await assert.rejects(installHostBundle(spec), SyntaxError);
    const pendingPath = "plugins/sage-kit/skills/sage-kit/SKILL.md";
    const marker = JSON.parse(await readFile(join(spec.bundleRoot, ".sage-kit-host-bundle.json"), "utf8"));
    assert.ok(marker.files.includes("plugins/sage-kit/a.txt"));
    assert.ok(!marker.files.includes(pendingPath), "an intended destination is not completed ownership");
    assert.ok(marker.pendingFiles.includes(pendingPath));
    const userFile = join(spec.bundleRoot, pendingPath);
    await mkdir(join(userFile, ".."), { recursive: true });
    await writeFile(userFile, "# user skill\n");
    await writeFile(join(pluginSource, "z-manifest.json"), JSON.stringify({ name: "sage-kit" }));
    await assert.rejects(installHostBundle(spec), (error) => error.code === "E_HOST_BUNDLE_UNOWNED");
    assert.equal(await readFile(userFile, "utf8"), "# user skill\n");
    const removed = await uninstallHostBundle({ bundleRoot: spec.bundleRoot, host: "codex" });
    assert.ok(removed.removed.includes(join(spec.bundleRoot, "plugins/sage-kit/a.txt")));
    assert.equal(await readFile(userFile, "utf8"), "# user skill\n");
  });

  it("stages a marketplace, plugin manifest, canonical skill copy and ownership marker", async () => {
    const dir = await tempDir("codex-install");
    const project = await initFakeProject(dir);
    const result = await installCodexHostBundle({ projectRoot: project });

    assert.equal(result.host, "codex");
    assert.equal(result.version, PACKAGE_VERSION);
    assert.equal(result.created, true);
    assert.equal(result.bundleRoot, codexHostBundleRoot(project));
    assert.equal(result.marketplaceRoot, result.bundleRoot);
    assert.equal(result.pluginRoot, join(result.bundleRoot, "plugins", "sage-kit"));
    assert.equal(result.marketplacePath, join(result.bundleRoot, ".agents", "plugins", "marketplace.json"));

    const marketplace = JSON.parse(await readFile(result.marketplacePath, "utf8"));
    assert.equal(marketplace.name, "sage-kit");
    assert.deepEqual(marketplace.plugins[0].source, { source: "local", path: "./plugins/sage-kit" });

    const manifest = JSON.parse(await readFile(join(result.pluginRoot, ".codex-plugin", "plugin.json"), "utf8"));
    assert.equal(manifest.name, "sage-kit");
    assert.equal(manifest.version, PACKAGE_VERSION);
    assert.equal(manifest.hooks, "./hooks/hooks.json");

    const stagedSkill = await readFile(join(result.skillPath, "SKILL.md"));
    const canonicalSkill = await readFile(CANONICAL_SKILL);
    assert.ok(stagedSkill.equals(canonicalSkill), "staged skill must be byte-identical to the canonical skill");

    const marker = JSON.parse(await readFile(join(result.bundleRoot, ".sage-kit-host-bundle.json"), "utf8"));
    assert.equal(marker.schemaVersion, 1);
    assert.equal(marker.host, "codex");
    assert.equal(marker.version, PACKAGE_VERSION);
    assert.deepEqual(marker.files, result.files);
    assert.ok(marker.files.includes("plugins/sage-kit/.codex-plugin/plugin.json"));
    assert.ok(marker.files.includes("plugins/sage-kit/skills/sage-kit/SKILL.md"));
    assert.ok(marker.files.includes(".agents/plugins/marketplace.json"));
    assert.ok(existsSync(join(result.pluginRoot, "hooks", "session-start.cjs")));
  });

  it("reinstall is idempotent and preserves user files in the bundle root", async () => {
    const dir = await tempDir("codex-idempotent");
    const project = await initFakeProject(dir);
    const first = await installCodexHostBundle({ projectRoot: project });
    await writeFile(join(first.bundleRoot, "user-note.txt"), "keep me\n", "utf8");
    const markerPath = join(first.bundleRoot, ".sage-kit-host-bundle.json");
    const legacyMarker = JSON.parse(await readFile(markerPath, "utf8"));
    delete legacyMarker.pendingFiles;
    await writeFile(markerPath, JSON.stringify(legacyMarker));
    const second = await installCodexHostBundle({ projectRoot: project });
    assert.equal(second.created, false);
    assert.deepEqual(second.files, first.files);
    assert.equal(await readFile(join(second.pluginRoot, "skills", "sage-kit", "SKILL.md"), "utf8"), await readFile(CANONICAL_SKILL, "utf8"));
    assert.equal(await readFile(join(first.bundleRoot, "user-note.txt"), "utf8"), "keep me\n");
    const skillFiles = await readdir(join(second.pluginRoot, "skills", "sage-kit"));
    assert.deepEqual(skillFiles, (await readdir(join(REPO_ROOT, "skills", "sage-kit"))).sort());
  });

  it("refuses to overwrite a directory it does not own", async () => {
    const dir = await tempDir("codex-unowned");
    const project = await initFakeProject(dir);
    const bundleRoot = codexHostBundleRoot(project);
    await mkdir(bundleRoot, { recursive: true });
    await writeFile(join(bundleRoot, "user-content.txt"), "mine\n", "utf8");
    await assert.rejects(
      () => installCodexHostBundle({ projectRoot: project }),
      (error) => error instanceof SageError && error.code === "E_HOST_BUNDLE_UNOWNED",
    );
    assert.equal(await readFile(join(bundleRoot, "user-content.txt"), "utf8"), "mine\n");
  });

  it("uninstall removes only owned files, keeps user files and is repeat-safe", async () => {
    const dir = await tempDir("codex-uninstall");
    const project = await initFakeProject(dir);
    const result = await installCodexHostBundle({ projectRoot: project });
    await writeFile(join(result.bundleRoot, "user-note.txt"), "keep me\n", "utf8");

    const uninstall = await uninstallCodexHostBundle({ projectRoot: project });
    assert.ok(uninstall.removed.some((path) => path.endsWith("SKILL.md")));
    assert.ok(!existsSync(result.marketplacePath));
    assert.ok(!existsSync(join(result.pluginRoot, ".codex-plugin", "plugin.json")));
    assert.ok(!existsSync(join(result.bundleRoot, ".sage-kit-host-bundle.json")));
    assert.equal(await readFile(join(result.bundleRoot, "user-note.txt"), "utf8"), "keep me\n");
    assert.ok(existsSync(result.bundleRoot), "bundle root must survive because a user file remains");
    assert.ok(uninstall.warnings.some((warning) => warning.includes("Kept files")));

    const second = await uninstallCodexHostBundle({ projectRoot: project });
    assert.deepEqual(second.removed, []);
    assert.ok(second.warnings.some((warning) => warning.includes("marker")));
    assert.equal(await readFile(join(result.bundleRoot, "user-note.txt"), "utf8"), "keep me\n");
  });

  it("does not adopt or delete user files nested inside the managed plugin subtree", async () => {
    const dir = await tempDir("codex-user-inside");
    const project = await initFakeProject(dir);
    const first = await installCodexHostBundle({ projectRoot: project });
    const userFile = join(first.pluginRoot, "user-zone", "nested.txt");
    await mkdir(join(first.pluginRoot, "user-zone"), { recursive: true });
    await writeFile(userFile, "user-owned\n", "utf8");

    const second = await installCodexHostBundle({ projectRoot: project });
    assert.equal(second.files.some((file) => file.includes("user-zone")), false);
    const uninstall = await uninstallCodexHostBundle({ projectRoot: project });
    assert.equal(await readFile(userFile, "utf8"), "user-owned\n");
    assert.ok(existsSync(userFile));
    assert.ok(uninstall.warnings.some((warning) => warning.includes("Kept files")));
  });

  it("clean uninstall deletes the whole bundle and repeats without error", async () => {
    const dir = await tempDir("codex-clean");
    const project = await initFakeProject(dir);
    const result = await installCodexHostBundle({ projectRoot: project });
    const uninstall = await uninstallCodexHostBundle({ projectRoot: project });
    assert.ok(uninstall.removed.includes(result.bundleRoot));
    assert.ok(!existsSync(result.bundleRoot));
    const second = await uninstallCodexHostBundle({ projectRoot: project });
    assert.deepEqual(second, { removed: [], kept: [], warnings: [] });
  });

  it("refuses an install whose destination ancestor is a symlink", async (t) => {
    const dir = await tempDir("codex-ancestor-link");
    const project = await initFakeProject(dir);
    const external = join(dir, "outside");
    await mkdir(external, { recursive: true });
    const bundleRoot = codexHostBundleRoot(project);
    await mkdir(bundleRoot, { recursive: true });
    try {
      await symlink(external, join(bundleRoot, "plugins"), "junction");
    } catch (error) {
      t.skip(`symlink/junction unavailable: ${String(error)}`);
      return;
    }
    await assert.rejects(
      () => installCodexHostBundle({ projectRoot: project }),
      (error) =>
        error instanceof SageError &&
        (error.code === "E_HOST_BUNDLE_ESCAPE" || error.code === "E_HOST_BUNDLE_UNOWNED"),
    );
    assert.deepEqual(await readdir(external), [], "install must not write through the link");
  });

  it("refuses to write through a symlink inside an owned bundle", async (t) => {
    const dir = await tempDir("codex-owned-link");
    const project = await initFakeProject(dir);
    const first = await installCodexHostBundle({ projectRoot: project });
    const external = join(dir, "outside-owned");
    await mkdir(external, { recursive: true });
    await rm(first.pluginRoot, { recursive: true, force: true });
    try {
      await symlink(external, first.pluginRoot, "junction");
    } catch (error) {
      t.skip(`symlink/junction unavailable: ${String(error)}`);
      return;
    }
    await assert.rejects(
      () => installCodexHostBundle({ projectRoot: project }),
      (error) => error instanceof SageError && error.code === "E_HOST_BUNDLE_ESCAPE",
    );
    assert.deepEqual(await readdir(external), [], "install must not write into the symlink target");
  });

  it("refuses a bundle whose .sage-kit/hosts ancestor is a symlink", async (t) => {
    const dir = await tempDir("codex-host-link");
    const project = await initFakeProject(dir);
    const external = join(dir, "outside-hosts");
    await mkdir(external, { recursive: true });
    const hosts = join(project, ".sage-kit", "hosts");
    await rm(hosts, { recursive: true, force: true });
    try {
      await symlink(external, hosts, "junction");
    } catch (error) {
      t.skip(`symlink/junction unavailable: ${String(error)}`);
      return;
    }
    await assert.rejects(
      () => installCodexHostBundle({ projectRoot: project }),
      (error) => error instanceof SageError && error.code === "E_HOST_BUNDLE_ESCAPE",
    );
    assert.deepEqual(await readdir(external), [], "install must not write through the hosts link");
  });

  it("keeps an unowned symlink instead of recursively deleting the bundle root", async (t) => {
    const dir = await tempDir("codex-kept-link");
    const project = await initFakeProject(dir);
    const result = await installCodexHostBundle({ projectRoot: project });
    const external = join(dir, "outside");
    await mkdir(external, { recursive: true });
    await writeFile(join(external, "keep.txt"), "keep\n", "utf8");
    try {
      await symlink(external, join(result.bundleRoot, "user-link"), "junction");
    } catch (error) {
      t.skip(`symlink/junction unavailable: ${String(error)}`);
      return;
    }
    const uninstall = await uninstallCodexHostBundle({ projectRoot: project });
    assert.ok(uninstall.warnings.some((warning) => warning.includes("Kept files")));
    assert.equal(await readFile(join(external, "keep.txt"), "utf8"), "keep\n");
    assert.ok(existsSync(join(result.bundleRoot, "user-link")));
  });

});

describe("claude host bundle", () => {
  it("stages a Claude marketplace, plugin manifest and canonical skill copy", async () => {
    const dir = await tempDir("claude-install");
    const project = await initFakeProject(dir);
    const result = await installClaudeHostBundle({ projectRoot: project });
    assert.equal(result.host, "claude");
    assert.equal(result.version, PACKAGE_VERSION);
    const manifest = JSON.parse(await readFile(join(result.pluginRoot, ".claude-plugin", "plugin.json"), "utf8"));
    assert.equal(manifest.name, "sage-kit");
    assert.equal(manifest.version, PACKAGE_VERSION);
    assert.deepEqual(manifest.hooks, ["./hooks/hooks.json"]);
    const marketplace = JSON.parse(await readFile(result.marketplacePath, "utf8"));
    assert.equal(marketplace.name, "sage-kit");
    assert.equal(marketplace.plugins[0].source, "./plugins/sage-kit");
    assert.ok((await readFile(join(result.skillPath, "SKILL.md"))).equals(await readFile(CANONICAL_SKILL)));
    assert.ok(existsSync(join(result.pluginRoot, "hooks", "session-start.cjs")));
    const uninstall = await uninstallClaudeHostBundle({ projectRoot: project });
    assert.ok(uninstall.removed.includes(result.bundleRoot));
    assert.ok(!existsSync(result.bundleRoot));
  });
});

describe("session-start bridge", () => {
  it("R11: plain Git repositories receive no SAGE context from either bridge", async () => {
    const dir = await tempDir("bridge-plain-git");
    const git = await runProcess("git", ["init", "-q", dir]);
    assert.equal(git.code, 0, git.stderr);
    for (const packageDir of [CODEX_PACKAGE, CLAUDE_PACKAGE]) {
      const result = await runBridge(packageDir, {
        stdin: hookPayload(dir), env: { SAGE_KIT_BIN: CLI },
      });
      assert.equal(result.code, 0);
      assert.deepEqual(parseBridgeJson(result.stdout), {});
    }
  });

  it("is a silent no-op in an uninitialized project and does not run the CLI", async () => {
    const dir = await tempDir("bridge-noop");
    const project = join(dir, "plain");
    await mkdir(project, { recursive: true });
    const touchFile = join(dir, "invoked.txt");
    const fake = await writeFakeCli(dir);
    const result = await runBridge(CODEX_PACKAGE, {
      stdin: hookPayload(project),
      env: { SAGE_KIT_BIN: fake, FAKE_MODE: "touch", FAKE_TOUCH: touchFile },
    });
    assert.equal(result.code, 0);
    assert.deepEqual(parseBridgeJson(result.stdout), {});
    assert.ok(!existsSync(touchFile), "bridge must not invoke the CLI before the project is initialized");
  });

  it("resolves an initialized linked worktree through the CLI instead of the ancestor scan", async () => {
    const dir = await tempDir("bridge-linked");
    const main = join(dir, "main");
    const linked = join(dir, "linked");
    await mkdir(main, { recursive: true });
    const git = (cwd, args) =>
      spawnSync("git", ["-C", cwd, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", ...args], {
        encoding: "utf8",
        timeout: 20_000,
        env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
      });
    assert.equal(spawnSync("git", ["init", "-b", "main", main], { encoding: "utf8", timeout: 20_000 }).status, 0);
    git(main, ["commit", "--allow-empty", "-m", "init"]);
    const init = await runProcess(process.execPath, [CLI, "init", "--host", "fake", "--scope", "project"], {
      cwd: main,
    });
    assert.equal(init.code, 0, init.stderr);
    const added = git(main, ["worktree", "add", "-b", "linked-branch", linked]);
    assert.equal(added.status, 0, added.stderr);

    const result = await runBridge(CODEX_PACKAGE, {
      stdin: hookPayload(linked),
      env: { SAGE_KIT_BIN: CLI },
    });
    assert.equal(result.code, 0);
    const output = parseBridgeJson(result.stdout);
    assert.ok(output.hookSpecificOutput?.additionalContext, "linked worktree must get the brief");
  });

  it("injects a bounded brief for an initialized project", async () => {
    const dir = await tempDir("bridge-bounded");
    const project = await initFakeProject(dir);
    const fake = await writeFakeCli(dir);
    const result = await runBridge(CODEX_PACKAGE, {
      stdin: hookPayload(project),
      env: { SAGE_KIT_BIN: fake, FAKE_BYTES: "10000" },
    });
    assert.equal(result.code, 0);
    const output = parseBridgeJson(result.stdout);
    assert.equal(output.hookSpecificOutput.hookEventName, "SessionStart");
    const context = output.hookSpecificOutput.additionalContext;
    assert.ok(typeof context === "string" && context.length > 0);
    assert.ok(Buffer.byteLength(context, "utf8") <= 2048, `context is ${Buffer.byteLength(context, "utf8")} bytes`);
    assert.ok(!context.endsWith("\uFFFD"), "truncation must not leave a broken UTF-8 code point");
  });

  it("honors SAGE_KIT_BRIEF_MAX_BYTES and resolves cwd from the hook payload", async () => {
    const dir = await tempDir("bridge-maxbytes");
    const project = await initFakeProject(dir);
    const fake = await writeFakeCli(dir);
    const result = await runBridge(CLAUDE_PACKAGE, {
      stdin: hookPayload(project),
      cwd: REPO_ROOT,
      env: { SAGE_KIT_BIN: fake, FAKE_MODE: "echo-cwd", SAGE_KIT_BRIEF_MAX_BYTES: "256" },
    });
    assert.equal(result.code, 0);
    const output = parseBridgeJson(result.stdout);
    const context = output.hookSpecificOutput.additionalContext;
    assert.ok(context.includes(project), "bridge must use cwd from the host hook payload");
    assert.ok(Buffer.byteLength(context, "utf8") <= 256);
  });

  it("fails open on CLI timeout, non-zero exit and malformed output", async () => {
    const dir = await tempDir("bridge-failopen");
    const project = await initFakeProject(dir);
    const fake = await writeFakeCli(dir);

    const started = Date.now();
    const timeout = await runBridge(CODEX_PACKAGE, {
      stdin: hookPayload(project),
      env: { SAGE_KIT_BIN: fake, FAKE_MODE: "sleep", SAGE_KIT_HOOK_TIMEOUT_MS: "300" },
    });
    assert.ok(Date.now() - started < 5_000);
    assert.equal(timeout.code, 0);
    assert.deepEqual(parseBridgeJson(timeout.stdout), {});

    for (const mode of ["fail", "malformed"]) {
      const result = await runBridge(CODEX_PACKAGE, {
        stdin: hookPayload(project),
        env: { SAGE_KIT_BIN: fake, FAKE_MODE: mode },
      });
      assert.equal(result.code, 0);
      assert.deepEqual(parseBridgeJson(result.stdout), {}, `mode=${mode} must fail open`);
    }
  });

  it("works against the real sage-kit CLI in an initialized project", async () => {
    const dir = await tempDir("bridge-real-cli");
    const project = join(dir, "project");
    await mkdir(project, { recursive: true });
    const init = await runProcess(process.execPath, [CLI, "init", "--host", "fake", "--scope", "project"], {
      cwd: project,
    });
    assert.equal(init.code, 0, init.stderr);
    const result = await runBridge(CODEX_PACKAGE, {
      stdin: hookPayload(project),
      env: { SAGE_KIT_BIN: CLI },
    });
    assert.equal(result.code, 0);
    const output = parseBridgeJson(result.stdout);
    const context = output.hookSpecificOutput.additionalContext;
    assert.match(context, /^# SAGE-Kit brief/);
    assert.match(context, /No task exists yet/);
  });
});

describe("codex host registration (real CLI, isolated CODEX_HOME)", { skip: !CODEX_AVAILABLE }, () => {
  it("registers, lists, removes and leaves the real Codex config untouched", async () => {
    const dir = await tempDir("codex-register");
    const project = await initFakeProject(dir);
    const result = await installCodexHostBundle({ projectRoot: project });
    const codexHome = join(dir, "codex-home");
    await mkdir(codexHome, { recursive: true });
    const realConfig = join(homedir(), ".codex", "config.toml");
    const realConfigBefore = existsSync(realConfig) ? await readFile(realConfig) : null;
    const env = { CODEX_HOME: codexHome };
    const codex = (args, stdin) => runProcess(CODEX_BIN, args, { env, stdin, timeoutMs: 120_000 });

    const addMarketplace = await codex(["plugin", "marketplace", "add", result.marketplaceRoot, "--json"]);
    assert.equal(addMarketplace.code, 0, addMarketplace.stderr);
    const added = JSON.parse(addMarketplace.stdout);
    assert.equal(added.marketplaceName, "sage-kit");

    const addPlugin = await codex(["plugin", "add", "sage-kit@sage-kit", "--json"]);
    assert.equal(addPlugin.code, 0, addPlugin.stderr);
    const installed = JSON.parse(addPlugin.stdout);
    assert.equal(installed.pluginId, "sage-kit@sage-kit");
    assert.equal(installed.version, PACKAGE_VERSION);
    assert.ok(existsSync(installed.installedPath), "codex must copy the plugin into its own cache");

    const config = await readFile(join(codexHome, "config.toml"), "utf8");
    assert.match(config, /\[plugins\."sage-kit@sage-kit"\]/);
    assert.match(config, /\[marketplaces\.sage-kit\]/);

    const list = await codex(["plugin", "list", "--json"]);
    assert.equal(list.code, 0);
    assert.ok(list.stdout.includes("sage-kit@sage-kit"));

    const remove = await codex(["plugin", "remove", "sage-kit@sage-kit", "--json"]);
    assert.equal(remove.code, 0, remove.stderr);
    const listAfter = await codex(["plugin", "list", "--json"]);
    assert.ok(!listAfter.stdout.includes("sage-kit@sage-kit"));

    const realConfigAfter = existsSync(realConfig) ? await readFile(realConfig) : null;
    assert.deepEqual(realConfigAfter, realConfigBefore, "CODEX_HOME isolation must keep the real config untouched");

    const uninstall = await uninstallCodexHostBundle({ projectRoot: project });
    assert.ok(!existsSync(result.bundleRoot));
    assert.ok(uninstall.removed.length > 0);
  });
});

it("host CLI stages and uninstalls a Codex bundle without touching host config", async () => {
  const dir = await tempDir("host-cli");
  const project = join(dir, "project");
  await mkdir(project, { recursive: true });
  const init = await runProcess(process.execPath, [CLI, "init", "--host", "fake", "--scope", "project"], {
    cwd: project,
  });
  assert.equal(init.code, 0, init.stderr);

  const install = await runProcess(process.execPath, [CLI, "host", "install", "--host", "codex", "--json"], {
    cwd: project,
  });
  assert.equal(install.code, 0, install.stderr);
  const installed = JSON.parse(install.stdout);
  assert.equal(installed.ok, true);
  assert.equal(installed.host, "codex");
  assert.ok(existsSync(join(project, ".sage-kit", "hosts", "codex", ".agents", "plugins", "marketplace.json")));

  const uninstall = await runProcess(process.execPath, [CLI, "host", "uninstall", "--host", "codex", "--json"], {
    cwd: project,
  });
  assert.equal(uninstall.code, 0, uninstall.stderr);
  assert.equal(existsSync(join(project, ".sage-kit", "hosts", "codex")), false);
});

it("S16-03: host uninstall uses its ownership marker after core uninstall removed config", async () => {
  for (const host of ["codex", "claude"]) {
    const project = await tempDir(`core-uninstall-${host}`);
    const run = (args) => runProcess(process.execPath, [CLI, ...args], { cwd: project });
    const init = await run(["init", "--host", host, "--scope", "project"]);
    assert.equal(init.code, 0, init.stderr);
    const installed = await run(["host", "install", "--host", host, "--json"]);
    assert.equal(installed.code, 0, installed.stderr);
    const bundleRoot = JSON.parse(installed.stdout).bundleRoot;
    const uninstalled = await run(["uninstall"]);
    assert.equal(uninstalled.code, 0, uninstalled.stderr);
    assert.equal(existsSync(join(project, ".sage-kit", "config.json")), false);
    const removed = await run(["host", "uninstall", "--host", host, "--project-root", project, "--json"]);
    assert.equal(removed.code, 0, removed.stderr);
    assert.equal(existsSync(bundleRoot), false);
  }
});
