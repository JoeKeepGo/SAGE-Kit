import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { it, mock } from "node:test";
import { acquireEvaluationLock, inspectEvaluationLock } from "../dist/rsi/lock.js";
import { runFixedCommand } from "../dist/rsi/process.js";

async function fixture() {
  const base = process.env.SAGE_KIT_TEST_TMPDIR ?? tmpdir();
  await fs.mkdir(base, { recursive: true });
  const root = await fs.mkdtemp(join(base, "sage-cleanup-"));
  return { root, store: { paths: { lockPath: join(root, "evaluation.lock") }, nowIso: () => new Date().toISOString() } };
}

it("R13: failed acquisition mutex cleanup rolls back the acquired evaluation lock", async () => {
  const { root, store } = await fixture();
  mock.method(fs, "rmdir", async () => { throw Object.assign(new Error("injected mutex cleanup failure"), { code: "EIO" }); });
  syncBuiltinESMExports();
  try {
    await assert.rejects(acquireEvaluationLock(store), (error) => error.code === "E_RSI_LOCK_FAILED" && /injected mutex/.test(error.message));
    assert.deepEqual(await inspectEvaluationLock(store), { state: "free" });
  } finally {
    mock.restoreAll();
    syncBuiltinESMExports();
    await fs.rm(root, { recursive: true, force: true });
  }
});

it("R13: failed rollback preserves both cleanup errors", async () => {
  const { root, store } = await fixture();
  const originalUnlink = fs.unlink;
  mock.method(fs, "rmdir", async () => { throw new Error("injected mutex cleanup failure"); });
  mock.method(fs, "unlink", async (path) => {
    if (path === store.paths.lockPath) throw new Error("injected evaluation lock rollback failure");
    return originalUnlink(path);
  });
  syncBuiltinESMExports();
  try {
    await assert.rejects(acquireEvaluationLock(store), (error) => {
      assert.ok(error instanceof AggregateError);
      assert.match(error.errors[0].message, /injected mutex cleanup/);
      assert.match(error.errors[1].message, /injected evaluation lock rollback/);
      return true;
    });
  } finally {
    mock.restoreAll();
    syncBuiltinESMExports();
    await fs.rm(root, { recursive: true, force: true });
  }
});

for (const detached of [false, true]) {
  it(`R12: an exited command with ${detached ? "escaped" : "inherited"} descendants cannot hold evaluation open`, {
    timeout: 15_000,
    skip: !detached && process.platform === "win32" ? "Windows sandbox does not reproduce inherited pipes with a non-detached child" : false,
  }, async () => {
    const { root, store } = await fixture();
    const pidFile = join(root, "descendant.pid");
    // The child inherits both output pipes, but the direct command exits first.
    const code = `const {spawn}=require('node:child_process'); const fs=require('node:fs');
      const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:['ignore',1,2],detached:${detached},windowsHide:true});
      fs.writeFileSync(${JSON.stringify(pidFile)},String(child.pid)); process.exit(0);`;
    const lock = await acquireEvaluationLock(store);
    let result;
    try {
      result = await runFixedCommand([process.execPath, "-e", code], root, { timeoutMs: 1000 });
      assert.equal(result.timedOut, true);
      assert.ok(result.durationMs < 10_000, `unexpected duration ${result.durationMs}`);
      if (detached || process.platform === "win32") {
        assert.match(result.stderr, /descendants may still be running/);
      } else {
        assert.doesNotMatch(result.stderr, /cleanup deadline expired/);
      }
    } finally {
      await lock.release();
      const pid = Number(await fs.readFile(pidFile, "utf8"));
      try { process.kill(pid, "SIGKILL"); } catch (error) { if (error.code !== "ESRCH") throw error; }
      const deadline = Date.now() + 2000;
      for (;;) {
        try { process.kill(pid, 0); } catch (error) { if (error.code === "ESRCH") break; throw error; }
        assert.ok(Date.now() < deadline, `fixture descendant ${pid} did not exit`);
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      assert.deepEqual(await inspectEvaluationLock(store), { state: "free" });
      await fs.rm(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 50 });
    }
  });
}
