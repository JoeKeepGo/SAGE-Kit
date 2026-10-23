import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, describe, it } from "node:test";
import {
  DEFAULT_RSI_LIMITS,
  acquireEvaluationLock,
  approve,
  createRollbackPoint,
  evaluateCandidate,
  openRsi,
  rejectProposal,
  requestApproval,
  rsiPaths,
  runOnce,
} from "../dist/rsi/index.js";

const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const BASE_COMMIT = "0123456789abcdef0123456789abcdef01234567";
const BASE_VERSION = "0.1.0";
const SKILL_MD = "# Fixture SKILL\n\nThis file must never be rewritten by RSI.\n";
const FIXED_TEST = [
  'import assert from "node:assert/strict";',
  'import { readFileSync } from "node:fs";',
  'import { it } from "node:test";',
  "",
  'it("candidate supplies the approved value", () => {',
  '  const value = readFileSync(new URL("../src/value.txt", import.meta.url), "utf8").trim();',
  '  assert.equal(value, "approved-value");',
  '  console.log("token=super-secret-value");',
  "});",
  "",
].join("\n");
const TEST_COMMAND = [process.execPath, "--test", "tests/check.test.mjs"];

const cleanups = [];
await mkdir(TEST_TMP_BASE, { recursive: true });

after(async () => {
  for (const cleanup of cleanups.reverse()) {
    await Promise.resolve()
      .then(cleanup)
      .catch(() => {});
  }
});

async function tempProject() {
  const dir = await mkdtemp(join(TEST_TMP_BASE, "sage-kit-rsi-"));
  cleanups.push(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

/** Minimal project the fixed fixture suite can run against, with no dependencies. */
async function writeFixtureProject() {
  const dir = await tempProject();
  const files = {
    "package.json": `${JSON.stringify(
      { name: "rsi-fixture", version: BASE_VERSION, type: "module", private: true },
      null,
      2,
    )}\n`,
    "skills/sage-kit/SKILL.md": SKILL_MD,
    "tests/check.test.mjs": FIXED_TEST,
    "src/keep.txt": "baseline\n",
  };
  for (const [relative, content] of Object.entries(files)) {
    const target = join(dir, ...relative.split("/"));
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, content, "utf8");
  }
  return dir;
}

function fixtureProposal(overrides = {}) {
  return {
    id: "prop-fixture-0001",
    feedbackRefs: [{ id: "feedback-1", url: "https://example.invalid/issues/1", title: "fixture feedback" }],
    baseVersion: BASE_VERSION,
    baseCommit: BASE_COMMIT,
    hypothesis: "Adding src/value.txt satisfies the fixed fixture suite.",
    scope: ["src/value.txt"],
    risks: ["fixture only"],
    validationPlan: "node --test tests/check.test.mjs",
    rollbackPlan: "git checkout the base commit",
    candidate: {
      builder: "fixture-builder",
      summary: "add the expected value file",
      files: [{ path: "src/value.txt", content: "approved-value\n" }],
    },
    ...overrides,
  };
}

function fakeClock(startIso = "2026-01-01T00:00:00.000Z") {
  let current = Date.parse(startIso);
  const clock = () => new Date(current);
  clock.advance = (ms) => {
    current += ms;
  };
  return clock;
}

async function expectRejects(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.equal(error.code, code, `expected ${code}, got ${error.code}: ${error.message}`);
    return true;
  });
}

describe("M3 RSI proposal store", () => {
  it("stores a fixture proposal and reloads it from the file-mode store", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    const proposal = await store.createProposal(fixtureProposal());
    assert.equal(proposal.status, "proposed");
    assert.equal(proposal.schemaVersion, 1);
    assert.equal(proposal.attempts, 0);
    assert.equal(proposal.feedbackRefs.length, 1);
    assert.equal(proposal.feedbackRefs[0].untrustedData, true);
    const proposalPath = join(rsiPaths(dir).proposalsDir, `${proposal.id}.json`);
    assert.ok(existsSync(proposalPath));
    assert.deepEqual(await openRsi(dir).getProposal(proposal.id), proposal);
    assert.equal((await store.listProposals()).length, 1);
    assert.equal((await store.listProposals({ status: "failed" })).length, 0);

    await expectRejects(store.createProposal(fixtureProposal()), "E_RSI_PROPOSAL_EXISTS");
    await expectRejects(
      store.createProposal(fixtureProposal({ id: "prop-bad-0001", hypothesis: "" })),
      "E_RSI_BAD_PROPOSAL",
    );
    await expectRejects(
      store.createProposal(fixtureProposal({ id: "prop-bad-0002", baseCommit: "not-a-commit" })),
      "E_RSI_BAD_PROPOSAL",
    );
    await expectRejects(
      store.createProposal(
        fixtureProposal({
          id: "prop-bad-0003",
          candidate: { files: [{ path: "../escape.txt", content: "x" }] },
        }),
      ),
      "E_RSI_UNSAFE_PATH",
    );
    await expectRejects(
      store.createProposal(
        fixtureProposal({ id: "prop-bad-0004", feedbackRefs: [{ url: "file:///etc/passwd" }] }),
      ),
      "E_RSI_BAD_PROPOSAL",
    );
  });

  it("reports corrupted records instead of returning partial data", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    await store.createProposal(fixtureProposal());
    const proposalPath = join(rsiPaths(dir).proposalsDir, "prop-fixture-0001.json");
    await writeFile(proposalPath, "{not json", "utf8");
    await expectRejects(store.getProposal("prop-fixture-0001"), "E_RSI_STORE_CORRUPT");
    await expectRejects(store.listProposals(), "E_RSI_STORE_CORRUPT");
  });
});

describe("M3 RSI candidate evaluation", () => {
  it("blocks a failing candidate and never auto-retries it", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-fail-0001",
        candidate: {
          builder: "fixture-builder",
          summary: "add the wrong value",
          files: [{ path: "src/value.txt", content: "wrong-value\n" }],
        },
      }),
    );
    const result = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "failed");
    assert.equal(result.evaluated, 1);
    assert.equal(result.proposalId, "prop-fail-0001");
    assert.equal(result.reasonCode, "E_RSI_TESTS_FAILED");

    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(evaluation.outcome, "failed");
    assert.equal(evaluation.ranTests, true);
    assert.notEqual(evaluation.exitCode, 0);
    assert.equal(evaluation.workspace.removed, true);
    assert.equal(existsSync(evaluation.workspace.tempDir), false);
    assert.match(`${evaluation.log.stdout}\n${evaluation.log.stderr}`, /not ok|fail/i);

    const proposal = await store.getProposal("prop-fail-0001");
    assert.equal(proposal.status, "failed");
    assert.equal(proposal.attempts, 1);
    assert.equal(proposal.evaluationId, evaluation.id);
    assert.equal(existsSync(join(dir, "src", "value.txt")), false, "candidate must not touch the source tree");
    await expectRejects(
      requestApproval({ projectRoot: dir, proposalId: proposal.id }),
      "E_RSI_NOT_AWAITING_APPROVAL",
    );

    // A failed candidate is not retried automatically: the next run is idle.
    assert.deepEqual(await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND }), {
      outcome: "idle",
      evaluated: 0,
    });
    assert.equal((await store.getProposal(proposal.id)).attempts, 1);
  });

  it("requires an explicit human approval token and rollback point for a passing candidate", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    await store.createProposal(fixtureProposal({ id: "prop-pass-0001" }));
    const result = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "passed");
    assert.equal(result.status, "awaiting_approval");
    assert.equal(result.proposalId, "prop-pass-0001");

    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(evaluation.outcome, "passed");
    assert.equal(evaluation.exitCode, 0);
    assert.equal(evaluation.ranTests, true);
    assert.equal(evaluation.diff.files, 1);
    assert.equal(evaluation.workspace.removed, true);
    assert.ok(evaluation.workspace.tempDir.length > 0);
    assert.ok(!evaluation.workspace.tempDir.startsWith(`${dir}`), "evaluation must run in a temp copy");
    assert.ok(evaluation.log.stdout.includes("[REDACTED]"), "credential-shaped log output must be redacted");
    assert.ok(!evaluation.log.stdout.includes("super-secret-value"));

    // No automatic approval, merge, publish or SKILL.md rewrite.
    assert.equal((await store.listApprovals()).length, 0);
    assert.equal(await readFile(join(dir, "skills", "sage-kit", "SKILL.md"), "utf8"), SKILL_MD);
    assert.equal(existsSync(join(dir, "src", "value.txt")), false, "candidate only applies inside the temp copy");

    const proposalId = "prop-pass-0001";
    await expectRejects(
      approve({
        projectRoot: dir,
        proposalId,
        approvalToken: "0".repeat(32),
        decidedBy: "human-reviewer",
        rollbackPointId: "rb-missing",
      }),
      "E_RSI_APPROVAL_NOT_REQUESTED",
    );

    const challenge = await requestApproval({ projectRoot: dir, proposalId });
    assert.match(challenge.approvalToken, /^[0-9a-f]{32}$/);
    const rollbackPoint = await createRollbackPoint({
      projectRoot: dir,
      baseCommit: BASE_COMMIT,
      baseVersion: BASE_VERSION,
      note: "fixture baseline",
    });
    assert.equal(rollbackPoint.rollbackCommand, `git checkout ${BASE_COMMIT}`);
    assert.ok(existsSync(join(rsiPaths(dir).rollbackPointsDir, `${rollbackPoint.id}.json`)));

    await expectRejects(
      approve({
        projectRoot: dir,
        proposalId,
        approvalToken: "f".repeat(32),
        decidedBy: "human-reviewer",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_APPROVAL_TOKEN_INVALID",
    );
    await expectRejects(
      approve({
        projectRoot: dir,
        proposalId,
        approvalToken: challenge.approvalToken,
        decidedBy: "   ",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_BAD_APPROVAL",
    );

    const foreignPoint = await createRollbackPoint({
      projectRoot: dir,
      baseCommit: "fedcba9876543210fedcba9876543210fedcba98",
      baseVersion: BASE_VERSION,
    });
    await expectRejects(
      approve({
        projectRoot: dir,
        proposalId,
        approvalToken: challenge.approvalToken,
        decidedBy: "human-reviewer",
        rollbackPointId: foreignPoint.id,
      }),
      "E_RSI_ROLLBACK_POINT_MISMATCH",
    );

    const approval = await approve({
      projectRoot: dir,
      proposalId,
      approvalToken: challenge.approvalToken,
      decidedBy: "human-reviewer",
      note: "evidence reviewed",
      rollbackPointId: rollbackPoint.id,
    });
    assert.equal(approval.decision, "approved");
    assert.equal(approval.decidedBy, "human-reviewer");
    assert.equal(approval.evaluationId, evaluation.id);
    assert.equal(approval.rollbackPointId, rollbackPoint.id);
    assert.equal(approval.rollbackCommand, `git checkout ${BASE_COMMIT}`);
    assert.ok(existsSync(join(rsiPaths(dir).approvalsDir, `${approval.id}.json`)));

    const approved = await store.getProposal(proposalId);
    assert.equal(approved.status, "approved");
    assert.equal(approved.approvalId, approval.id);
    assert.equal(approved.rollbackPointId, rollbackPoint.id);
    assert.equal(approved.approvalChallenge, undefined);

    await expectRejects(
      approve({
        projectRoot: dir,
        proposalId,
        approvalToken: challenge.approvalToken,
        decidedBy: "human-reviewer",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_ALREADY_DECIDED",
    );
    await expectRejects(
      evaluateCandidate({ projectRoot: dir, proposalId, testCommand: TEST_COMMAND }),
      "E_RSI_BAD_TRANSITION",
    );
  });

  it("expires one-time approval challenges", async () => {
    const dir = await writeFixtureProject();
    const clock = fakeClock();
    const store = openRsi(dir, { clock });
    await store.createProposal(fixtureProposal({ id: "prop-expire-0001" }));
    const result = await runOnce({ store, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "passed");
    const challenge = await requestApproval({
      store,
      proposalId: "prop-expire-0001",
      approvalTtlMs: 60_000,
    });
    const rollbackPoint = await createRollbackPoint({
      store,
      baseCommit: BASE_COMMIT,
      baseVersion: BASE_VERSION,
    });
    clock.advance(61_000);
    await expectRejects(
      approve({
        store,
        proposalId: "prop-expire-0001",
        approvalToken: challenge.approvalToken,
        decidedBy: "human-reviewer",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_APPROVAL_EXPIRED",
    );
    assert.equal((await store.getProposal("prop-expire-0001")).status, "awaiting_approval");
  });

  it("rejects a candidate that modifies protected evaluation assets", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    const testFileBefore = await readFile(join(dir, "tests", "check.test.mjs"), "utf8");
    await store.createProposal(
      fixtureProposal({
        id: "prop-protected-0001",
        candidate: {
          builder: "fixture-builder",
          files: [{ path: "tests/check.test.mjs", content: "// fake passing test\n" }],
        },
      }),
    );
    const result = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "failed");
    assert.equal(result.reasonCode, "E_RSI_PROTECTED_ASSET");
    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(evaluation.ranTests, false);
    assert.equal(evaluation.exitCode, null);
    assert.equal(evaluation.workspace, undefined);
    assert.deepEqual(evaluation.protectedAssets.changed, ["tests/check.test.mjs"]);
    assert.equal(evaluation.protectedAssets.ok, false);
    assert.equal(await readFile(join(dir, "tests", "check.test.mjs"), "utf8"), testFileBefore);
    assert.equal((await store.getProposal("prop-protected-0001")).status, "failed");
  });

  it("enforces diff-size and file-count budgets before running the suite", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    const bigContent = Array.from({ length: DEFAULT_RSI_LIMITS.maxChangedLines + 1 }, (_item, index) => `line-${index}`).join("\n");
    await store.createProposal(
      fixtureProposal({
        id: "prop-budget-0001",
        candidate: { files: [{ path: "src/big.txt", content: bigContent }] },
      }),
    );
    const first = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(first.outcome, "failed");
    assert.equal(first.reasonCode, "E_RSI_DIFF_TOO_LARGE");
    const firstEvaluation = await store.getEvaluation(first.evaluationId);
    assert.equal(firstEvaluation.ranTests, false);
    assert.ok(firstEvaluation.diff.changedLines > DEFAULT_RSI_LIMITS.maxChangedLines);

    const manyFiles = Array.from({ length: DEFAULT_RSI_LIMITS.maxCandidateFiles + 1 }, (_item, index) => ({
      path: `src/generated-${index}.txt`,
      content: "x\n",
    }));
    await store.createProposal(
      fixtureProposal({ id: "prop-budget-0002", candidate: { files: manyFiles } }),
    );
    const second = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(second.outcome, "failed");
    assert.equal(second.reasonCode, "E_RSI_DIFF_TOO_LARGE");
    const secondEvaluation = await store.getEvaluation(second.evaluationId);
    assert.equal(secondEvaluation.diff.files, DEFAULT_RSI_LIMITS.maxCandidateFiles + 1);
    assert.equal(secondEvaluation.ranTests, false);
  });

  it("kills a timed-out fixed command and records the timeout", async () => {
    const dir = await writeFixtureProject();
    await writeFile(join(dir, "hang.mjs"), "setTimeout(() => {}, 60_000);\n", "utf8");
    const store = openRsi(dir);
    await store.createProposal(fixtureProposal({ id: "prop-timeout-0001" }));
    const result = await runOnce({
      projectRoot: dir,
      testCommand: [process.execPath, "hang.mjs"],
      limits: { evaluationTimeoutMs: 700 },
    });
    assert.equal(result.outcome, "failed");
    assert.equal(result.reasonCode, "E_RSI_EVAL_TIMEOUT");
    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(evaluation.timedOut, true);
    assert.equal(evaluation.exitCode, null);
    assert.equal(evaluation.ranTests, true);
    assert.equal(evaluation.workspace.removed, true);
  });
});

describe("M3 RSI scheduling and isolation boundaries", () => {
  it("allows one candidate at a time and takes over a stale evaluation lock", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    await store.createProposal(fixtureProposal({ id: "prop-lock-0001" }));
    const lock = await acquireEvaluationLock(store);
    try {
      await expectRejects(runOnce({ projectRoot: dir, testCommand: TEST_COMMAND }), "E_RSI_EVALUATION_LOCKED");
    } finally {
      await lock.release();
    }
    const result = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(result.proposalId, "prop-lock-0001");
    assert.equal(result.outcome, "passed");

    // A lock left by a dead process is stale and taken over (crash recovery).
    const dead = spawnSync(process.execPath, ["-e", "process.exit(0)"]);
    assert.equal(dead.status, 0);
    await writeFile(
      rsiPaths(dir).lockPath,
      `${JSON.stringify({ pid: dead.pid, owner: "dead-evaluator", startedAt: new Date().toISOString() })}\n`,
      "utf8",
    );
    await store.createProposal(
      fixtureProposal({
        id: "prop-lock-0002",
        candidate: { files: [{ path: "src/value.txt", content: "wrong-value\n" }] },
      }),
    );
    const second = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(second.proposalId, "prop-lock-0002");
    assert.equal(second.outcome, "failed");
  });

  it("runs only when called, one candidate per call, and never auto-approves", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    assert.deepEqual(await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND }), {
      outcome: "idle",
      evaluated: 0,
    });

    await store.createProposal(fixtureProposal({ id: "prop-one-0001" }));
    await store.createProposal(
      fixtureProposal({
        id: "prop-two-0001",
        candidate: { files: [{ path: "src/value.txt", content: "wrong-value\n" }] },
      }),
    );
    const first = await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND });
    assert.equal(first.evaluated, 1);
    assert.equal(first.proposalId, "prop-one-0001");
    assert.equal((await store.getProposal("prop-one-0001")).status, "awaiting_approval");
    assert.equal((await store.getProposal("prop-two-0001")).status, "proposed");
    assert.equal((await store.listEvaluations()).length, 1);
    assert.equal((await store.listApprovals()).length, 0);
  });

  it("records an explicit human rejection without a rollback point", async () => {
    const dir = await writeFixtureProject();
    const store = openRsi(dir);
    await store.createProposal(fixtureProposal({ id: "prop-reject-0001" }));
    const rejection = await rejectProposal({
      projectRoot: dir,
      proposalId: "prop-reject-0001",
      decidedBy: "human-reviewer",
      reason: "out of scope",
    });
    assert.equal(rejection.decision, "rejected");
    assert.equal(rejection.decidedBy, "human-reviewer");
    const proposal = await store.getProposal("prop-reject-0001");
    assert.equal(proposal.status, "rejected");
    assert.equal(proposal.approvalId, rejection.id);
    await expectRejects(
      requestApproval({ projectRoot: dir, proposalId: "prop-reject-0001" }),
      "E_RSI_ALREADY_DECIDED",
    );
    assert.equal((await runOnce({ projectRoot: dir, testCommand: TEST_COMMAND })).outcome, "idle");
  });

  it("keeps the RSI source free of network calls, model SDKs and schedulers", async () => {
    const sourceDir = fileURLToPath(new URL("../src/rsi/", import.meta.url));
    const files = (await readdir(sourceDir)).filter((name) => name.endsWith(".ts"));
    assert.ok(files.length >= 8, `expected the RSI module files, found ${files.join(", ")}`);
    for (const file of files) {
      const source = await readFile(join(sourceDir, file), "utf8");
      assert.doesNotMatch(
        source,
        /from\s+"node:(?:http|https|net|dns|tls|dgram)"/,
        `${file} must not import network modules`,
      );
      assert.doesNotMatch(source, /\bfetch\s*\(/, `${file} must not call fetch`);
      assert.doesNotMatch(source, /\bsetInterval\s*\(/, `${file} must not schedule a default timer`);
      assert.doesNotMatch(source, /\b(?:openai|anthropic|deepseek)\b/i, `${file} must not import a model SDK`);
    }
  });
});
