import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  MAX_BRIEF_BYTES,
  MIN_BRIEF_BYTES,
  clampBriefBytes,
  configuredRoot,
  discoverRoot,
} from "../packages/dsh-plugin/lib.js";
import { findProjectRoot } from "../dist/core/paths.js";
import { initSageKit } from "../dist/core/install.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const plugin = join(root, "packages", "dsh-plugin");

test("plugin lib clamps brief bytes to the documented range", () => {
  assert.equal(clampBriefBytes(undefined), 2048);
  assert.equal(clampBriefBytes(4096), 4096);
  assert.equal(clampBriefBytes(-1), MIN_BRIEF_BYTES);
  assert.equal(clampBriefBytes(999999), MAX_BRIEF_BYTES);
  assert.equal(clampBriefBytes(12.9), MIN_BRIEF_BYTES);
  assert.equal(clampBriefBytes(Number.NaN), 2048);
});

test("plugin lib discovers an initialized project from a descendant", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-lib-"));
  try {
    const project = join(temp, "project");
    const nested = join(project, "a", "b");
    await mkdir(join(project, ".sage-kit"), { recursive: true });
    await mkdir(nested, { recursive: true });
    await writeFile(join(project, ".sage-kit", "config.json"), "{}");
    assert.equal(discoverRoot(nested), project);
    assert.equal(configuredRoot(project), project);
    assert.throws(() => configuredRoot("relative/project"), /absolute path/);
    assert.equal(configuredRoot(undefined), undefined);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("F06: does not treat submodule or separate-git-dir gitfiles as linked worktrees", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-gitfile-"));
  try {
    // Submodule: .git file points under the superproject's .git/modules, but
    // the submodule directory itself is the repository root.
    const superproject = join(temp, "main");
    const submodule = join(superproject, "vendor", "lib");
    await mkdir(join(superproject, ".git", "modules", "lib"), { recursive: true });
    await mkdir(submodule, { recursive: true });
    await writeFile(join(submodule, ".git"), "gitdir: ../../.git/modules/lib\n", "utf8");
    assert.equal(discoverRoot(submodule), submodule);
    assert.equal(await findProjectRoot(submodule), submodule);

    // Separate git dir: the working tree contains the gitfile, the metadata
    // directory lives elsewhere and must not become the project root.
    const worktree = join(temp, "repo");
    const metadata = join(temp, "metadata");
    await mkdir(worktree, { recursive: true });
    await mkdir(metadata, { recursive: true });
    await writeFile(join(worktree, ".git"), `gitdir: ${metadata}\n`, "utf8");
    assert.equal(discoverRoot(worktree), worktree);
    assert.equal(await findProjectRoot(worktree), worktree);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("F06b: resolves a linked worktree of a separate-git-dir repository to its main worktree", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-separate-"));
  const git = (cwd, args) =>
    execFileSync("git", ["-C", cwd, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", ...args], {
      encoding: "utf8",
      timeout: 20_000,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
    });
  try {
    const repo = join(temp, "repo");
    const metadata = join(temp, "metadata");
    await mkdir(repo, { recursive: true });
    execFileSync("git", ["init", "--separate-git-dir", metadata, repo], { encoding: "utf8", timeout: 20_000 });
    await writeFile(join(repo, "README.md"), "fixture\n", "utf8");
    git(repo, ["add", "-A"]);
    git(repo, ["commit", "-m", "init"]);
    await initSageKit({ projectRoot: repo, host: "fake", scope: "project", home: temp });
    const linked = join(temp, "linked");
    git(repo, ["worktree", "add", "-b", "linked-branch", linked]);
    assert.equal(discoverRoot(linked), repo, "plugin must use the main worktree, not the git metadata");
    assert.equal(await findProjectRoot(linked), repo, "CLI must use the same main worktree");
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("F06f: strict init resolution rejects an unmapped linked worktree", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-strict-"));
  const git = (cwd, args) =>
    execFileSync("git", ["-C", cwd, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", ...args], {
      encoding: "utf8",
      timeout: 20_000,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
    });
  try {
    const repo = join(temp, "repo");
    await mkdir(repo, { recursive: true });
    execFileSync("git", ["init", "-b", "main", repo], { encoding: "utf8", timeout: 20_000 });
    git(repo, ["commit", "--allow-empty", "-m", "init"]);
    const linked = join(temp, "linked");
    git(repo, ["worktree", "add", "-b", "linked-branch", linked]);
    await assert.rejects(
      () => findProjectRoot(linked, { strict: true }),
      (error) => error.code === "E_PROJECT_ROOT_UNRESOLVED",
      "init must not silently create a second state root in a linked worktree",
    );
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("F06e: a separate git dir named .git never becomes the project root", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-dotgit-"));
  const git = (cwd, args) =>
    execFileSync("git", ["-C", cwd, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", ...args], {
      encoding: "utf8",
      timeout: 20_000,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
    });
  try {
    const repo = join(temp, "repo");
    const metadataRoot = join(temp, "metadata-root");
    const metadata = join(metadataRoot, ".git");
    await mkdir(repo, { recursive: true });
    await mkdir(metadataRoot, { recursive: true });
    execFileSync("git", ["init", "-b", "main", "--separate-git-dir", metadata, repo], {
      encoding: "utf8",
      timeout: 20_000,
    });
    await writeFile(join(repo, "README.md"), "fixture\n", "utf8");
    git(repo, ["add", "-A"]);
    git(repo, ["commit", "-m", "init"]);
    const linked = join(temp, "linked");
    git(repo, ["worktree", "add", "-b", "linked-branch", linked]);
    const pluginRoot = discoverRoot(linked);
    const cliRoot = await findProjectRoot(linked);
    assert.notEqual(pluginRoot, metadata, "plugin must not use the git metadata dir");
    assert.notEqual(pluginRoot, metadataRoot, "plugin must not use the metadata dir's parent");
    assert.notEqual(cliRoot, metadata, "CLI must not use the git metadata dir");
    assert.notEqual(cliRoot, metadataRoot, "CLI must not use the metadata dir's parent");
    assert.equal(pluginRoot, cliRoot, "plugin and CLI must agree");
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("F06d: ignores a stale registry that names an unrelated repository at a reused path", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-stale-"));
  const git = (cwd, args) =>
    execFileSync("git", ["-C", cwd, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", ...args], {
      encoding: "utf8",
      timeout: 20_000,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
    });
  try {
    const repo = join(temp, "repo");
    const metadata = join(temp, "metadata");
    await mkdir(repo, { recursive: true });
    execFileSync("git", ["init", "-b", "main", "--separate-git-dir", metadata, repo], { encoding: "utf8", timeout: 20_000 });
    await writeFile(join(repo, "README.md"), "fixture\n", "utf8");
    git(repo, ["add", "-A"]);
    git(repo, ["commit", "-m", "init"]);
    await initSageKit({ projectRoot: repo, host: "fake", scope: "project", home: temp });
    const linked = join(temp, "linked");
    git(repo, ["worktree", "add", "-b", "linked-branch", linked]);

    const moved = join(temp, "repo-moved");
    await rename(repo, moved);
    // Reuse the old path for a different repository with its own SAGE-Kit state.
    await mkdir(repo, { recursive: true });
    execFileSync("git", ["init", "-b", "main", repo], { encoding: "utf8", timeout: 20_000 });
    await writeFile(join(repo, "README.md"), "other\n", "utf8");
    git(repo, ["add", "-A"]);
    git(repo, ["commit", "-m", "other init"]);
    await initSageKit({ projectRoot: repo, host: "fake", scope: "project", home: temp });

    const pluginRoot = discoverRoot(linked);
    const cliRoot = await findProjectRoot(linked);
    assert.notEqual(pluginRoot, repo, "plugin must not follow a stale registry into another repository");
    assert.notEqual(cliRoot, repo, "CLI must not follow a stale registry into another repository");
    assert.equal(pluginRoot, cliRoot, "plugin and CLI must still agree after ignoring the stale registry");
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("F06c: resolves a linked worktree of a submodule to the submodule worktree", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-submodule-"));
  const git = (cwd, args) =>
    execFileSync("git", ["-C", cwd, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", ...args], {
      encoding: "utf8",
      timeout: 20_000,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
    });
  try {
    const sub = join(temp, "library");
    await mkdir(sub, { recursive: true });
    execFileSync("git", ["init", "-b", "main", sub], { encoding: "utf8", timeout: 20_000 });
    await writeFile(join(sub, "index.js"), "export const x = 1;\n", "utf8");
    git(sub, ["add", "-A"]);
    git(sub, ["commit", "-m", "init library"]);

    const superproject = join(temp, "app");
    await mkdir(superproject, { recursive: true });
    execFileSync("git", ["init", "-b", "main", superproject], { encoding: "utf8", timeout: 20_000 });
    await writeFile(join(superproject, "README.md"), "fixture\n", "utf8");
    git(superproject, ["add", "-A"]);
    git(superproject, ["commit", "-m", "init app"]);
    git(superproject, ["-c", "protocol.file.allow=always", "submodule", "add", sub, "vendor/library"]);
    git(superproject, ["commit", "-m", "add submodule"]);
    const submodule = join(superproject, "vendor", "library");
    await initSageKit({ projectRoot: submodule, host: "fake", scope: "project", home: temp });

    const linked = join(temp, "linked-submodule");
    git(submodule, ["worktree", "add", "-b", "linked-submodule", linked]);
    assert.equal(discoverRoot(linked), submodule, "plugin must use the submodule worktree, not .git/modules");
    assert.equal(await findProjectRoot(linked), submodule, "CLI must use the same submodule worktree");
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("plugin and CLI resolve the same project root, including linked worktrees", async () => {
  const temp = await mkdtemp(join(tmpdir(), "sage-plugin-root-"));
  try {
    const project = join(temp, "project");
    const nested = join(project, "a", "b");
    await mkdir(join(project, ".git"), { recursive: true });
    await mkdir(join(project, ".sage-kit"), { recursive: true });
    await mkdir(nested, { recursive: true });
    await writeFile(join(project, ".sage-kit", "config.json"), "{}");
    assert.equal(discoverRoot(nested), project);
    assert.equal(await findProjectRoot(nested), project);

    // Simulate a linked task worktree: .git is a file, .sage-kit is absent.
    const worktree = join(project, ".sage-kit", "worktrees", "task-a");
    await mkdir(join(project, ".git", "worktrees", "task-a"), { recursive: true });
    await mkdir(worktree, { recursive: true });
    await writeFile(join(worktree, ".git"), "gitdir: ../../../.git/worktrees/task-a\n", "utf8");
    assert.equal(discoverRoot(join(worktree, "nested")), project);
    assert.equal(await findProjectRoot(join(worktree, "nested")), project);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

test("plugin manifest keeps host peers optional and the DSH upper bound prerelease-safe", async () => {
  const manifest = JSON.parse(await readFile(join(plugin, "package.json"), "utf8"));
  assert.equal(manifest.name, "sage-kit-dsh");
  assert.equal(manifest.engines.dsh, ">=0.2.1-rc.2 <0.3.0-0");
  assert.equal(manifest.peerDependenciesMeta["@deepseek-ai/dsh-tools"].optional, true);
  assert.equal(manifest.peerDependenciesMeta["sage-kit"], undefined);
  assert.deepEqual(manifest.files, ["index.js", "lib.js", "cordis.patch.yml", "README.md", "LICENSE"]);
  assert.equal(manifest.dependencies, undefined);
});

test("plugin source does not declare an undeclared DSH message form", async () => {
  const source = await readFile(join(plugin, "index.js"), "utf8");
  assert.doesNotMatch(source, /form:\s*["']brief["']/);
  assert.match(source, /source:\s*\{\s*kind:\s*["']sage-kit["']\s*\}/);
});
