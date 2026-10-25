/**
 * Core task RSI marker + read-only RSI gate tests.
 *
 * The gate must be usable by any host adapter through the stable library
 * entrypoint, and it must stay read-only: no evaluation, no approval, no
 * write of any kind, even when records are missing or corrupt.
 */
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";
import { checkRsiGate } from "../dist/index.js";
import { ensureStateDirs, statePaths } from "../dist/core/paths.js";
import { createTask, listTasks, listTasksStrict, readTask } from "../dist/core/tasks.js";
import { rsiPaths } from "../dist/rsi/paths.js";
import { openRsi } from "../dist/rsi/store.js";
import { RSI_SCHEMA_VERSION } from "../dist/rsi/types.js";

const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const BASE_COMMIT = "0123456789abcdef0123456789abcdef01234567";
const cleanups = [];
await mkdir(TEST_TMP_BASE, { recursive: true });

after(async () => {
  for (const cleanup of cleanups.reverse()) {
    await Promise.resolve()
      .then(cleanup)
      .catch(() => {});
  }
});

async function tempDir() {
  const dir = await mkdtemp(join(TEST_TMP_BASE, "sage-kit-rsi-gate-"));
  cleanups.push(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

async function taskPaths() {
  const root = await tempDir();
  const paths = statePaths(root);
  await ensureStateDirs(paths);
  return { root, paths };
}

function proposalInput(overrides = {}) {
  return {
    id: "prop-gate-0001",
    feedbackRefs: [],
    baseVersion: "1.0.0",
    baseCommit: BASE_COMMIT,
    hypothesis: "Gate fixture proposal.",
    scope: ["src/value.txt"],
    risks: [],
    validationPlan: "node --test tests/check.test.mjs",
    rollbackPlan: "git checkout the base commit",
    candidate: { files: [{ path: "src/value.txt", content: "approved-value\n" }] },
    ...overrides,
  };
}

function evaluationRecord({ id = "eval-gate-0001", proposalId, outcome = "passed" } = {}) {
  const passed = outcome === "passed";
  const run = {
    index: 1,
    kind: "candidate",
    applied: true,
    ranTests: true,
    outcome,
    ...(passed ? {} : { reasonCode: "E_RSI_TESTS_FAILED", reasonMessage: "fixed command exited 1" }),
    exitCode: passed ? 0 : 1,
    signal: null,
    timedOut: false,
    durationMs: 5,
    protectedAssets: { paths: ["tests"], ok: true, changed: [] },
    log: { stdout: "", stderr: "", truncated: false },
    worktree: { kind: "git-worktree", path: "/tmp/sage-kit-gate-worktree", removed: true },
  };
  return {
    schemaVersion: RSI_SCHEMA_VERSION,
    id,
    proposalId,
    attempt: 1,
    startedAt: "2026-01-01T00:00:00.000Z",
    finishedAt: "2026-01-01T00:00:01.000Z",
    baseCommit: BASE_COMMIT,
    repeats: 1,
    command: ["node", "--test", "tests/check.test.mjs"],
    outcome,
    ...(passed ? {} : { reasonCode: "E_RSI_TESTS_FAILED", reasonMessage: "fixed command exited 1" }),
    ranTests: true,
    exitCode: passed ? 0 : 1,
    signal: null,
    timedOut: false,
    durationMs: 5,
    diff: { files: 1, changedLines: 1, limits: { maxFiles: 20, maxChangedLines: 500 } },
    protectedAssets: { paths: ["tests"], ok: true, changed: [] },
    log: { stdout: "", stderr: "", truncated: false },
    runs: [run],
    baseline: { runs: [], passedRuns: 0, failedRuns: 0, outcome: "not_run" },
    comparison: {
      candidateRuns: 1,
      baselineRuns: 0,
      candidatePassedRuns: passed ? 1 : 0,
      baselinePassedRuns: 0,
      noWeakerThanBaseline: passed,
    },
  };
}

function approvalRecord({ id = "appr-gate-0001", proposalId, decision = "approved", evaluationId } = {}) {
  return {
    schemaVersion: RSI_SCHEMA_VERSION,
    id,
    proposalId,
    decision,
    decidedBy: "human-reviewer",
    decidedAt: "2026-01-01T00:00:02.000Z",
    ...(evaluationId === undefined ? {} : { evaluationId }),
  };
}

/** Seed one fully approved proposal (approved + passed evaluation + approval). */
async function seedApproved(root, overrides = {}) {
  const store = openRsi(root);
  const proposalId = overrides.proposalId ?? "prop-gate-0001";
  const evaluationId = overrides.evaluationId ?? "eval-gate-0001";
  const approvalId = overrides.approvalId ?? "appr-gate-0001";
  const proposal = await store.createProposal(proposalInput({ id: proposalId }));
  await store.saveEvaluation(
    evaluationRecord({
      id: evaluationId,
      proposalId,
      outcome: overrides.evaluationOutcome ?? "passed",
    }),
  );
  await store.saveProposal({
    ...proposal,
    status: overrides.proposalStatus ?? "approved",
    evaluationId,
    approvalId,
    decidedAt: "2026-01-01T00:00:02.000Z",
  });
  await store.saveApproval(
    approvalRecord({
      id: approvalId,
      proposalId: overrides.approvalProposalId ?? proposalId,
      decision: overrides.approvalDecision ?? "approved",
      evaluationId: overrides.approvalEvaluationId ?? evaluationId,
    }),
  );
  return { proposalId, evaluationId, approvalId };
}

/** Read every file under `root` so a read-only claim can be asserted. */
async function snapshotTree(root) {
  const files = {};
  async function walk(dir, prefix) {
    const entries = await readdir(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = join(dir, entry.name);
      if (entry.isDirectory()) await walk(full, relative);
      else files[relative] = await readFile(full, "utf8");
    }
  }
  try {
    await walk(root, "");
  } catch (error) {
    if (error.code === "ENOENT") return {};
    throw error;
  }
  return files;
}

async function expectRejects(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.equal(error.code, code, `expected ${code}, got ${error.code}: ${error.message}`);
    return true;
  });
}

describe("Task.rsiProposalId (core file mode)", () => {
  it("persists and reloads a marked task", async () => {
    const { paths } = await taskPaths();
    const task = await createTask(paths, {
      id: "task-gate-0001",
      title: "Implement an approved RSI proposal",
      rsiProposalId: "prop-gate-0001",
    });
    assert.equal(task.schemaVersion, 1);
    assert.equal(task.rsiProposalId, "prop-gate-0001");

    const onDisk = JSON.parse(await readFile(join(paths.tasksDir, "task-gate-0001.json"), "utf8"));
    assert.equal(onDisk.rsiProposalId, "prop-gate-0001");
    assert.deepEqual(await readTask(paths, "task-gate-0001"), task);
    assert.equal((await listTasks(paths))[0].rsiProposalId, "prop-gate-0001");
  });

  it("keeps ordinary tasks unchanged (field absent, schemaVersion 1)", async () => {
    const { paths } = await taskPaths();
    const task = await createTask(paths, { id: "task-plain-0001", title: "Ordinary P0 task" });
    assert.equal(task.schemaVersion, 1);
    assert.equal("rsiProposalId" in task, false);
    const onDisk = JSON.parse(await readFile(join(paths.tasksDir, "task-plain-0001.json"), "utf8"));
    assert.equal("rsiProposalId" in onDisk, false);
    assert.deepEqual(await readTask(paths, "task-plain-0001"), task);
  });

  it("rejects invalid proposal ids before writing a task", async () => {
    const { paths } = await taskPaths();
    const invalid = ["", "   ", "Bad Id", "UPPER", "../escape", "prop/../../x", `prop-${"a".repeat(70)}`];
    for (const rsiProposalId of invalid) {
      await expectRejects(
        createTask(paths, { id: "task-bad-rsi-0001", title: "bad", rsiProposalId }),
        "E_BAD_TASK",
      );
    }
    assert.deepEqual(await listTasks(paths), []);
    // Trimming is accepted; the stored value is the canonical id.
    const task = await createTask(paths, {
      id: "task-trim-0001",
      title: "trim",
      rsiProposalId: "  prop-gate-0001  ",
    });
    assert.equal(task.rsiProposalId, "prop-gate-0001");
  });

  it("rejects a persisted task whose rsiProposalId is malformed", async () => {
    const { paths } = await taskPaths();
    const now = "2026-01-01T00:00:00.000Z";
    await writeFile(
      join(paths.tasksDir, "task-bad-file-0001.json"),
      JSON.stringify({
        schemaVersion: 1,
        id: "task-bad-file-0001",
        title: "bad file",
        description: "",
        status: "ready",
        acceptance: [],
        evidence: [],
        rsiProposalId: "BAD ID",
        createdAt: now,
        updatedAt: now,
      }),
      "utf8",
    );
    await expectRejects(readTask(paths, "task-bad-file-0001"), "E_BAD_TASK_FILE");
  });

  it("strict task listing fails closed while the display listing stays tolerant", async () => {
    const { paths } = await taskPaths();
    await createTask(paths, { id: "task-good-0001", title: "good task" });
    await writeFile(join(paths.tasksDir, "task-broken-0001.json"), "{not json", "utf8");
    assert.deepEqual((await listTasks(paths)).map((task) => task.id), ["task-good-0001"]);
    await expectRejects(listTasksStrict(paths), "E_BAD_JSON");
  });

  it("keeps the duplicated core id regex in sync with src/rsi/validate.ts", async () => {
    // core/tasks.ts duplicates RSI_ID_PATTERN to avoid a core -> rsi import;
    // this pins both patterns to the same accepted/rejected sample set.
    const { RSI_ID_PATTERN } = await import("../dist/rsi/validate.js");
    const { paths } = await taskPaths();
    const samples = [
      "prop-gate-0001",
      "a",
      "a".repeat(64),
      "Bad Id",
      "-leading-dash",
      "prop_underscore",
      "PROP-UPPER",
      "a".repeat(65),
    ];
    for (const [index, sample] of samples.entries()) {
      const expected = RSI_ID_PATTERN.test(sample);
      const created = createTask(paths, {
        id: `task-sync-${String(index).padStart(4, "0")}`,
        title: "id sync",
        rsiProposalId: sample,
      });
      if (expected) {
        assert.equal((await created).rsiProposalId, sample);
      } else {
        await expectRejects(created, "E_BAD_TASK");
      }
    }
  });
});

describe("checkRsiGate (read-only release gate)", () => {
  it("is exported from the stable library entrypoint", async () => {
    assert.equal(typeof checkRsiGate, "function");
  });

  it("reports a missing proposal without throwing", async () => {
    const root = await tempDir();
    const result = await checkRsiGate(root, "prop-gate-0001");
    assert.deepEqual(result, {
      ok: false,
      reason: "proposal-not-found",
      proposalId: "prop-gate-0001",
    });
    // A missing project directory behaves like a missing record, not a crash.
    assert.equal((await checkRsiGate(join(root, "missing-dir"), "prop-gate-0001")).reason, "proposal-not-found");
  });

  it("reports an invalid proposal id without touching the store", async () => {
    const root = await tempDir();
    for (const proposalId of ["", "Bad Id", "../escape"]) {
      const result = await checkRsiGate(root, proposalId);
      assert.equal(result.ok, false);
      assert.equal(result.reason, "invalid-proposal-id");
      assert.equal(result.proposalId, proposalId);
    }
    assert.deepEqual(await snapshotTree(join(root, ".sage-kit")), {});
  });

  it("blocks a proposal that is not approved", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    await store.createProposal(proposalInput());
    const result = await checkRsiGate(root, "prop-gate-0001");
    assert.deepEqual(result, {
      ok: false,
      reason: "proposal-not-approved",
      proposalId: "prop-gate-0001",
      status: "proposed",
    });
  });

  it("blocks approved proposals without evaluation evidence", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await store.saveProposal({ ...proposal, status: "approved" });
    assert.deepEqual(await checkRsiGate(root, proposal.id), {
      ok: false,
      reason: "evaluation-missing",
      proposalId: proposal.id,
      status: "approved",
    });

    // A dangling evaluationId is the same normal failure, not an exception.
    await store.saveProposal({ ...proposal, status: "approved", evaluationId: "eval-missing-0001" });
    const dangling = await checkRsiGate(root, proposal.id);
    assert.equal(dangling.ok, false);
    assert.equal(dangling.reason, "evaluation-missing");
  });

  it("blocks approved proposals whose evaluation failed", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await store.saveEvaluation(evaluationRecord({ proposalId: proposal.id, outcome: "failed" }));
    await store.saveProposal({
      ...proposal,
      status: "approved",
      evaluationId: "eval-gate-0001",
      approvalId: "appr-gate-0001",
    });
    await store.saveApproval(approvalRecord({ proposalId: proposal.id, evaluationId: "eval-gate-0001" }));
    const result = await checkRsiGate(root, proposal.id);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "evaluation-not-passed");
    assert.equal(result.status, "approved");
  });

  it("blocks passed proposals without an approval record", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await store.saveEvaluation(evaluationRecord({ proposalId: proposal.id }));
    await store.saveProposal({
      ...proposal,
      status: "approved",
      evaluationId: "eval-gate-0001",
    });
    const result = await checkRsiGate(root, proposal.id);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "approval-missing");
  });

  it("blocks a rejected approval record", async () => {
    const root = await tempDir();
    const { proposalId } = await seedApproved(root, { approvalDecision: "rejected" });
    const result = await checkRsiGate(root, proposalId);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "approval-not-approved");
  });

  it("blocks an approval record that authorizes a different evaluation", async () => {
    const root = await tempDir();
    const { proposalId } = await seedApproved(root, { approvalEvaluationId: "eval-other-0001" });
    const result = await checkRsiGate(root, proposalId);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "approval-evaluation-mismatch");
  });

  it("blocks an approval without an evaluation binding", async () => {
    const root = await tempDir();
    const { proposalId } = await seedApproved(root, { approvalEvaluationId: "" });
    const result = await checkRsiGate(root, proposalId);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "approval-evaluation-mismatch");
  });

  it("rejects a proposal file whose internal id differs from its filename", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await writeFile(
      join(rsiPaths(root).proposalsDir, `${proposal.id}.json`),
      JSON.stringify({ ...proposal, id: "prop-other-0001" }, null, 2),
      "utf8",
    );
    const result = await checkRsiGate(root, proposal.id);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "proposal-unreadable");
  });

  it("rejects an evaluation file whose internal id differs from its filename", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await mkdir(rsiPaths(root).evaluationsDir, { recursive: true });
    await writeFile(
      join(rsiPaths(root).evaluationsDir, "eval-gate-0001.json"),
      JSON.stringify({ ...evaluationRecord({ proposalId: proposal.id }), id: "eval-other-0001" }, null, 2),
      "utf8",
    );
    await store.saveProposal({
      ...proposal,
      status: "approved",
      evaluationId: "eval-gate-0001",
      approvalId: "appr-gate-0001",
    });
    const result = await checkRsiGate(root, proposal.id);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "evaluation-unreadable");
  });

  it("rejects an approval file whose internal id differs from its filename", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await store.saveEvaluation(evaluationRecord({ proposalId: proposal.id }));
    await store.saveProposal({
      ...proposal,
      status: "approved",
      evaluationId: "eval-gate-0001",
      approvalId: "appr-gate-0001",
    });
    await mkdir(rsiPaths(root).approvalsDir, { recursive: true });
    await writeFile(
      join(rsiPaths(root).approvalsDir, "appr-gate-0001.json"),
      JSON.stringify({ ...approvalRecord({ proposalId: proposal.id }), id: "appr-other-0001" }, null, 2),
      "utf8",
    );
    const result = await checkRsiGate(root, proposal.id);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "approval-unreadable");
  });

  it("reports corrupt proposal/evaluation records instead of throwing", async () => {
    const root = await tempDir();
    const store = openRsi(root);
    const proposal = await store.createProposal(proposalInput());
    await store.saveEvaluation(evaluationRecord({ proposalId: proposal.id }));
    await store.saveProposal({
      ...proposal,
      status: "approved",
      evaluationId: "eval-gate-0001",
      approvalId: "appr-gate-0001",
    });
    await store.saveApproval(approvalRecord({ proposalId: proposal.id, evaluationId: "eval-gate-0001" }));

    await writeFile(join(rsiPaths(root).evaluationsDir, "eval-gate-0001.json"), "{not json", "utf8");
    const corruptEvaluation = await checkRsiGate(root, proposal.id);
    assert.equal(corruptEvaluation.ok, false);
    assert.equal(corruptEvaluation.reason, "evaluation-unreadable");

    await writeFile(join(rsiPaths(root).proposalsDir, `${proposal.id}.json`), "{not json", "utf8");
    const corruptProposal = await checkRsiGate(root, proposal.id);
    assert.equal(corruptProposal.ok, false);
    assert.equal(corruptProposal.reason, "proposal-unreadable");
  });

  it("passes only for approved + passed evaluation + approved matching approval, and writes nothing", async () => {
    const root = await tempDir();
    const { proposalId } = await seedApproved(root);
    const before = await snapshotTree(root);
    const result = await checkRsiGate(root, proposalId);
    assert.deepEqual(result, { ok: true, reason: "ok", proposalId, status: "approved" });
    const after = await snapshotTree(root);
    assert.deepEqual(after, before, "checkRsiGate must be read-only");
  });
});
