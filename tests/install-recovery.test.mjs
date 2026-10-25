import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { it } from "node:test";
import { initSageKit, uninstallSageKit } from "../dist/core/install.js";

it("N06: init clearly rejects a preserved skill directory missing SKILL.md and keeps user files", async () => {
  const tmpBase = process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
  await mkdir(tmpBase, { recursive: true });
  const projectRoot = await mkdtemp(join(tmpBase, "install-recovery-"));
  try {
    const options = { projectRoot, host: "fake", scope: "project", instructions: false };
    const first = await initSageKit(options);
    const userFile = join(first.skillPath, "user-notes.txt");
    await writeFile(userFile, "keep me\n");
    await uninstallSageKit({ projectRoot });
    await assert.rejects(
      initSageKit(options),
      (error) => error.code === "E_SKILL_INCOMPLETE" && /SKILL.md/.test(error.message),
    );
    assert.equal(await readFile(userFile, "utf8"), "keep me\n");
    await assert.rejects(readFile(join(projectRoot, ".sage-kit", "config.json")), { code: "ENOENT" });
  } finally {
    await rm(projectRoot, { recursive: true, force: true });
  }
});
