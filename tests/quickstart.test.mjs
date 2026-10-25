import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { access, mkdtemp, mkdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const bash = process.env.SAGE_TEST_BASH ?? "bash";
const shellPath = (path) => path.replaceAll("\\", "/");

test("R10: quickstart refuses children of a dangling DSH home symlink", async (t) => {
  const available = spawnSync(bash, ["--version"], { timeout: 5_000, encoding: "utf8" });
  if (available.error?.code === "ENOENT") return t.skip("bash is unavailable (set SAGE_TEST_BASH to test a specific installation)");
  assert.equal(available.status, 0, available.error?.message ?? available.stderr);
  const temp = await mkdtemp(join(tmpdir(), "sage-quickstart-link-"));
  try {
    const home = join(temp, "home");
    const target = join(temp, "profile-target");
    const bin = join(temp, "bin");
    await mkdir(home);
    await mkdir(bin);
    try {
      await symlink(target, join(home, ".dsh"), process.platform === "win32" ? "junction" : "dir");
    } catch (error) {
      if (error.code === "EPERM") return t.skip("symlink creation is not permitted");
      throw error;
    }
    // Only prerequisite commands run. The npm stub also stops an unfixed
    // script before it can build, pack, or install anything.
    for (const [name, body] of [
      ["node", 'if [ "$1" = "-p" ]; then echo 24; else echo v24.22.0; fi'],
      ["npm", "exit 99"],
      ["dsh", "echo 0.2.1-rc.2"],
      ["pnpm", "echo 10.34.8"],
    ]) {
      await writeFile(join(bin, name), "#!/usr/bin/env bash\n" + body + "\n", { mode: 0o755 });
    }
    const result = spawnSync(bash, [shellPath(join(root, "scripts", "quickstart-dsh.sh")), "--workdir", shellPath(join(home, ".dsh", "work"))], {
      encoding: "utf8",
      timeout: 10_000,
      env: {
        ...process.env,
        HOME: shellPath(home),
        PATH: bin + (process.platform === "win32" ? ";" : ":") + process.env.PATH,
        DSH_BIN: shellPath(join(bin, "dsh")),
        PNPM_BIN: shellPath(join(bin, "pnpm")),
      },
    });
    assert.equal(result.status, 1, result.error?.message ?? result.stderr);
    assert.match(result.stderr, /refusing to touch the user's DSH profile/);
    await assert.rejects(access(target), { code: "ENOENT" });
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});
