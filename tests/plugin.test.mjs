import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
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
