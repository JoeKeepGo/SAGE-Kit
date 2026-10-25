import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { access, mkdir, mkdtemp, readFile, readdir, rm, symlink, utimes, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { after, describe, it } from "node:test";
import {
  DEFAULT_REPEATS,
  DEFAULT_RSI_LIMITS,
  RSI_SCHEMA_VERSION,
  acquireEvaluationLock,
  approve,
  createRollbackPoint,
  evaluateCandidate,
  exportEvaluationSummary,
  openRsi,
  recoverInterruptedEvaluations,
  recordEvaluationInControl,
  rejectProposal,
  requestApproval,
  rsiPaths,
  runOnce,
} from "../dist/rsi/index.js";
import { openControl } from "../dist/control/index.js";

const TEST_TMP_BASE =
  process.env.SAGE_KIT_TEST_TMPDIR ?? join(homedir(), ".cache", "sage-kit-tests");
const REPO_ROOT = fileURLToPath(new URL("..", import.meta.url));
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

function git(cwd, args) {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    timeout: 60_000,
    env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
  });
  if (result.status !== 0) {
    throw new Error(`git ${args.join(" ")} failed: ${result.stderr || result.stdout}`);
  }
  return result.stdout.trim();
}

async function writeFixtureFiles(dir, { baselinePasses = false } = {}) {
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
  if (baselinePasses) files["src/value.txt"] = "approved-value\n";
  for (const [relative, content] of Object.entries(files)) {
    const target = join(dir, ...relative.split("/"));
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, content, "utf8");
  }
}

/** A real git fixture repo: committed baseline files plus `baseCommit`. */
async function writeFixtureRepo({ baselinePasses = false } = {}) {
  const dir = await tempProject();
  await writeFixtureFiles(dir, { baselinePasses });
  git(dir, ["init", "-q"]);
  git(dir, ["config", "user.email", "rsi-fixture@example.invalid"]);
  git(dir, ["config", "user.name", "RSI Fixture"]);
  git(dir, ["config", "commit.gpgsign", "false"]);
  git(dir, ["add", "-A"]);
  git(dir, ["commit", "-q", "-m", "fixture baseline"]);
  const baseCommit = git(dir, ["rev-parse", "HEAD"]);
  return { dir, baseCommit };
}

function fixtureProposal(overrides = {}) {
  return {
    id: "prop-fixture-0001",
    feedbackRefs: [{ id: "feedback-1", url: "https://example.invalid/issues/1", title: "fixture feedback" }],
    baseVersion: BASE_VERSION,
    baseCommit: "0123456789abcdef0123456789abcdef01234567",
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

async function expectRejects(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.equal(error.code, code, `expected ${code}, got ${error.code}: ${error.message}`);
    return true;
  });
}

function gitStatus(dir) {
  return git(dir, ["status", "--porcelain"]);
}

async function listEvaluations(dir) {
  const indexPath = rsiPaths(dir).evaluationsDir;
  if (!existsSync(indexPath)) return [];
  const names = await readdir(indexPath);
  return names.filter((name) => name.endsWith(".json"));
}

async function worktreesGone(evaluation, projectRoot) {
  const runs = [...(evaluation.baseline?.runs ?? []), ...evaluation.runs];
  assert.ok(runs.length > 0);
  for (const run of runs) {
    assert.equal(run.worktree.kind, "git-worktree");
    assert.equal(run.worktree.removed, true, `run ${run.kind}#${run.index} worktree must be removed`);
    assert.equal(existsSync(run.worktree.path), false, "worktree directory must be gone after evaluation");
    assert.ok(
      !resolve(run.worktree.path).startsWith(`${resolve(projectRoot)}${sep}`),
      "worktree lives outside the fixture project",
    );
    assert.ok(resolve(run.worktree.path).startsWith(resolve(tmpdir())), "worktree lives in the OS temp directory");
  }
}

describe("M3 RSI proposal store", () => {
  it("stores a v2 fixture proposal and reloads it from the file-mode store", async () => {
    const dir = await tempProject();
    const store = openRsi(dir);
    const proposal = await store.createProposal(fixtureProposal());
    assert.equal(proposal.status, "proposed");
    assert.equal(proposal.schemaVersion, RSI_SCHEMA_VERSION);
    assert.equal(proposal.schemaVersion, 2);
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
    const dir = await tempProject();
    const store = openRsi(dir);
    await store.createProposal(fixtureProposal());
    const proposalPath = join(rsiPaths(dir).proposalsDir, "prop-fixture-0001.json");
    await writeFile(proposalPath, "{not json", "utf8");
    await expectRejects(store.getProposal("prop-fixture-0001"), "E_RSI_STORE_CORRUPT");
    await expectRejects(store.listProposals(), "E_RSI_STORE_CORRUPT");
  });
});

describe("M3 RSI git-worktree evaluation", () => {
  it("refuses to evaluate outside a git repository, before touching the proposal", async () => {
    const dir = await tempProject();
    const store = openRsi(dir);
    await writeFixtureFiles(dir);
    await store.createProposal(fixtureProposal());
    await expectRejects(
      evaluateCandidate({ projectRoot: dir, proposalId: "prop-fixture-0001", testCommand: TEST_COMMAND }),
      "E_RSI_NOT_GIT_REPO",
    );
    const proposal = await store.getProposal("prop-fixture-0001");
    assert.equal(proposal.status, "proposed");
    assert.equal(proposal.attempts, 0);
    assert.deepEqual(await listEvaluations(dir), []);
  });

  it("rejects an unknown base commit without burning the single attempt", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    const missing = "0".repeat(40);
    await store.createProposal(fixtureProposal({ id: "prop-missing-commit", baseCommit: missing }));
    await expectRejects(
      evaluateCandidate({
        projectRoot: repo.dir,
        proposalId: "prop-missing-commit",
        testCommand: TEST_COMMAND,
      }),
      "E_RSI_BAD_BASE_COMMIT",
    );
    const proposal = await store.getProposal("prop-missing-commit");
    assert.equal(proposal.status, "proposed");
    assert.equal(proposal.attempts, 0);
    assert.deepEqual(await listEvaluations(repo.dir), []);
  });

  it("blocks a failing candidate, records baseline evidence and never retries automatically", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-fail-0001",
        baseCommit: repo.baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "add the wrong value",
          files: [{ path: "src/value.txt", content: "wrong-value\n" }],
        },
      }),
    );
    const result = await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "failed");
    assert.equal(result.evaluated, 1);
    assert.equal(result.proposalId, "prop-fail-0001");
    assert.equal(result.reasonCode, "E_RSI_TESTS_FAILED");
    assert.equal(result.status, "failed");

    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(evaluation.schemaVersion, 2);
    assert.equal(evaluation.baseCommit, repo.baseCommit);
    assert.equal(evaluation.repeats, DEFAULT_REPEATS);
    assert.equal(evaluation.outcome, "failed");
    assert.equal(evaluation.ranTests, true);
    assert.notEqual(evaluation.exitCode, 0);
    assert.equal(evaluation.baseline.outcome, "failed");
    assert.equal(evaluation.baseline.runs.length, 1);
    assert.equal(evaluation.baseline.passedRuns, 0);
    assert.equal(evaluation.runs.length, 1);
    assert.equal(evaluation.runs[0].kind, "candidate");
    assert.equal(evaluation.comparison.candidatePassedRuns, 0);
    assert.equal(evaluation.comparison.baselinePassedRuns, 0);
    assert.equal(evaluation.comparison.noWeakerThanBaseline, true);
    assert.match(`${evaluation.log.stdout}\n${evaluation.log.stderr}`, /not ok|fail/i);
    await worktreesGone(evaluation, repo.dir);

    const proposal = await store.getProposal("prop-fail-0001");
    assert.equal(proposal.status, "failed");
    assert.equal(proposal.attempts, 1);
    assert.equal(proposal.evaluationId, evaluation.id);
    assert.equal(existsSync(join(repo.dir, "src", "value.txt")), false, "candidate must not touch the source tree");
    await expectRejects(
      requestApproval({ projectRoot: repo.dir, proposalId: proposal.id }),
      "E_RSI_NOT_AWAITING_APPROVAL",
    );

    // A failed candidate is not retried automatically: the next run is idle.
    assert.deepEqual(await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND }), {
      outcome: "idle",
      evaluated: 0,
    });
    assert.equal((await store.getProposal(proposal.id)).attempts, 1);
  });

  it("passes only with baseline comparison and still requires a one-time human approval", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    const proposalId = "prop-pass-0001";
    await store.createProposal(fixtureProposal({ id: proposalId, baseCommit: repo.baseCommit }));
    const result = await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "passed");
    assert.equal(result.status, "awaiting_approval");
    assert.equal(result.proposalId, proposalId);

    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(evaluation.outcome, "passed");
    assert.equal(evaluation.exitCode, 0);
    assert.equal(evaluation.ranTests, true);
    assert.equal(evaluation.diff.files, 1);
    assert.equal(evaluation.diff.limits.maxFiles, DEFAULT_RSI_LIMITS.maxCandidateFiles);
    assert.equal(evaluation.baseline.outcome, "failed", "the baseline commit lacks src/value.txt");
    assert.equal(evaluation.baseline.passedRuns, 0);
    assert.equal(evaluation.comparison.candidatePassedRuns, 1);
    assert.equal(evaluation.comparison.baselinePassedRuns, 0);
    assert.equal(evaluation.comparison.noWeakerThanBaseline, true);
    assert.equal(evaluation.protectedAssets.ok, true);
    assert.ok(evaluation.log.stdout.includes("[REDACTED]"), "credential-shaped log output must be redacted");
    assert.ok(!evaluation.log.stdout.includes("super-secret-value"));
    await worktreesGone(evaluation, repo.dir);

    // No automatic approval, merge, publish or SKILL.md rewrite.
    assert.equal((await store.listApprovals()).length, 0);
    assert.equal(await readFile(join(repo.dir, "skills", "sage-kit", "SKILL.md"), "utf8"), SKILL_MD);
    assert.equal(existsSync(join(repo.dir, "src", "value.txt")), false, "candidate only applies inside the temp worktree");

    await expectRejects(
      approve({
        projectRoot: repo.dir,
        proposalId,
        approvalToken: "0".repeat(32),
        decidedBy: "human-reviewer",
        rollbackPointId: "rb-missing",
      }),
      "E_RSI_APPROVAL_NOT_REQUESTED",
    );

    const challenge = await requestApproval({ projectRoot: repo.dir, proposalId });
    assert.match(challenge.approvalToken, /^[0-9a-f]{32}$/);
    const rollbackPoint = await createRollbackPoint({
      projectRoot: repo.dir,
      baseCommit: repo.baseCommit,
      baseVersion: BASE_VERSION,
      note: "fixture baseline",
    });
    assert.equal(rollbackPoint.rollbackCommand, `git checkout ${repo.baseCommit}`);
    assert.ok(existsSync(join(rsiPaths(repo.dir).rollbackPointsDir, `${rollbackPoint.id}.json`)));

    await expectRejects(
      approve({
        projectRoot: repo.dir,
        proposalId,
        approvalToken: "f".repeat(32),
        decidedBy: "human-reviewer",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_APPROVAL_TOKEN_INVALID",
    );
    await expectRejects(
      approve({
        projectRoot: repo.dir,
        proposalId,
        approvalToken: challenge.approvalToken,
        decidedBy: "   ",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_BAD_APPROVAL",
    );

    const foreignPoint = await createRollbackPoint({
      projectRoot: repo.dir,
      baseCommit: "fedcba9876543210fedcba9876543210fedcba98",
      baseVersion: BASE_VERSION,
    });
    await expectRejects(
      approve({
        projectRoot: repo.dir,
        proposalId,
        approvalToken: challenge.approvalToken,
        decidedBy: "human-reviewer",
        rollbackPointId: foreignPoint.id,
      }),
      "E_RSI_ROLLBACK_POINT_MISMATCH",
    );

    const approval = await approve({
      projectRoot: repo.dir,
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
    assert.equal(approval.rollbackCommand, `git checkout ${repo.baseCommit}`);
    assert.ok(existsSync(join(rsiPaths(repo.dir).approvalsDir, `${approval.id}.json`)));

    const approved = await store.getProposal(proposalId);
    assert.equal(approved.status, "approved");
    assert.equal(approved.approvalId, approval.id);
    assert.equal(approved.rollbackPointId, rollbackPoint.id);
    assert.equal(approved.approvalChallenge, undefined);

    // The one-time token cannot approve twice.
    await expectRejects(
      approve({
        projectRoot: repo.dir,
        proposalId,
        approvalToken: challenge.approvalToken,
        decidedBy: "human-reviewer",
        rollbackPointId: rollbackPoint.id,
      }),
      "E_RSI_ALREADY_DECIDED",
    );
    assert.equal(await readFile(join(repo.dir, "skills", "sage-kit", "SKILL.md"), "utf8"), SKILL_MD);
  });

  it("runs tests inside throwaway worktrees and ignores uncommitted main-tree changes", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    // Uncommitted change in the main working tree: must never be evaluated.
    await writeFile(join(repo.dir, "src", "value.txt"), "approved-value\n", "utf8");
    await store.createProposal(fixtureProposal({ id: "prop-isolate-0001", baseCommit: repo.baseCommit }));

    const result = await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "passed");
    const evaluation = await store.getEvaluation(result.evaluationId);
    assert.equal(
      evaluation.baseline.outcome,
      "failed",
      "baseline must run on the committed base tree, not the dirty working tree",
    );
    assert.equal(evaluation.comparison.baselinePassedRuns, 0);
    assert.equal(existsSync(join(repo.dir, "src", "value.txt")), true);
    assert.equal(await readFile(join(repo.dir, "src", "value.txt"), "utf8"), "approved-value\n");
    await worktreesGone(evaluation, repo.dir);

    const status = gitStatus(repo.dir);
    assert.match(status, /\?\? src\/value\.txt/, "untracked main-tree file is still there");
    assert.match(status, /\?\? \.sage-kit\//);
    assert.doesNotMatch(status, /^ ?M /m, "no tracked file was modified in the main tree");
  });

  it("evaluates bounded repeats and stores every baseline/candidate run", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({ id: "prop-repeat-0001", baseCommit: repo.baseCommit }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-repeat-0001",
      testCommand: TEST_COMMAND,
      repeats: 3,
    });
    assert.equal(evaluation.repeats, 3);
    assert.equal(evaluation.baseline.runs.length, 3);
    assert.equal(evaluation.runs.length, 3);
    assert.deepEqual(
      evaluation.baseline.runs.map((run) => run.kind),
      ["baseline", "baseline", "baseline"],
    );
    assert.deepEqual(
      evaluation.runs.map((run) => run.kind),
      ["candidate", "candidate", "candidate"],
    );
    assert.deepEqual(evaluation.baseline.runs.map((run) => run.index), [1, 2, 3]);
    assert.deepEqual(evaluation.runs.map((run) => run.index), [1, 2, 3]);
    assert.equal(evaluation.baseline.outcome, "failed");
    assert.equal(evaluation.baseline.passedRuns, 0);
    assert.equal(evaluation.outcome, "passed");
    assert.equal(evaluation.comparison.candidatePassedRuns, 3);
    assert.equal(evaluation.comparison.baselinePassedRuns, 0);
    assert.equal(evaluation.comparison.noWeakerThanBaseline, true);
    assert.ok(evaluation.runs.every((run) => run.durationMs >= 0));
    await worktreesGone(evaluation, repo.dir);
  });

  it("rejects out-of-bounds repeat counts before evaluation starts", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({ id: "prop-repeat-bad", baseCommit: repo.baseCommit }),
    );
    await expectRejects(
      evaluateCandidate({
        projectRoot: repo.dir,
        proposalId: "prop-repeat-bad",
        testCommand: TEST_COMMAND,
        repeats: 0,
      }),
      "E_RSI_BAD_LIMIT",
    );
    await expectRejects(
      evaluateCandidate({
        projectRoot: repo.dir,
        proposalId: "prop-repeat-bad",
        testCommand: TEST_COMMAND,
        repeats: DEFAULT_RSI_LIMITS.maxRepeats + 1,
      }),
      "E_RSI_BAD_LIMIT",
    );
    await expectRejects(
      evaluateCandidate({
        projectRoot: repo.dir,
        proposalId: "prop-repeat-bad",
        testCommand: TEST_COMMAND,
        repeats: 3,
        limits: { maxRepeats: 2 },
      }),
      "E_RSI_BAD_LIMIT",
    );
    const proposal = await store.getProposal("prop-repeat-bad");
    assert.equal(proposal.status, "proposed");
    assert.equal(proposal.attempts, 0);
  });

  it("rejects a candidate that tries to modify protected test assets", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-protected-0001",
        baseCommit: repo.baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "weaken the evaluator suite",
          files: [{ path: "tests/check.test.mjs", content: "// weakened\n" }],
        },
      }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-protected-0001",
      testCommand: TEST_COMMAND,
    });
    assert.equal(evaluation.outcome, "failed");
    assert.equal(evaluation.reasonCode, "E_RSI_PROTECTED_ASSET");
    assert.equal(evaluation.ranTests, false);
    assert.equal(evaluation.runs.length, 0);
    assert.equal(evaluation.baseline.outcome, "not_run");
    assert.equal(await readFile(join(repo.dir, "tests", "check.test.mjs"), "utf8"), FIXED_TEST);
    assert.equal((await store.getProposal("prop-protected-0001")).status, "failed");
  });

  it("enforces diff/file budgets before running the fixed suite", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-budget-0001",
        baseCommit: repo.baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "too many files",
          files: [
            { path: "src/value.txt", content: "approved-value\n" },
            { path: "src/extra.txt", content: "extra\n" },
          ],
        },
      }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-budget-0001",
      testCommand: TEST_COMMAND,
      limits: { maxCandidateFiles: 1 },
    });
    assert.equal(evaluation.outcome, "failed");
    assert.equal(evaluation.reasonCode, "E_RSI_DIFF_TOO_LARGE");
    assert.equal(evaluation.ranTests, false);
    assert.equal(evaluation.runs.length, 0);
    assert.equal(evaluation.diff.files, 2);
    assert.equal(evaluation.diff.limits.maxFiles, 1);
    assert.equal((await store.getProposal("prop-budget-0001")).status, "failed");
  });

  it("times out a hanging fixed command, records it and cleans every worktree", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({ id: "prop-timeout-0001", baseCommit: repo.baseCommit }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-timeout-0001",
      testCommand: [process.execPath, "-e", "setTimeout(() => {}, 30000)"],
      limits: { evaluationTimeoutMs: 500 },
    });
    assert.equal(evaluation.outcome, "failed");
    assert.equal(evaluation.reasonCode, "E_RSI_EVAL_TIMEOUT");
    assert.equal(evaluation.timedOut, true);
    assert.equal(evaluation.ranTests, true);
    assert.equal(evaluation.baseline.runs.length, 1);
    assert.equal(evaluation.baseline.runs[0].timedOut, true);
    assert.equal(evaluation.runs[0].timedOut, true);
    assert.match(evaluation.reasonMessage, /500 ms/);
    await worktreesGone(evaluation, repo.dir);
    assert.equal((await store.getProposal("prop-timeout-0001")).status, "failed");
  });

  it("evaluates exactly one candidate per runOnce and leaves later proposals untouched", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-aaa-0001",
        baseCommit: repo.baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "first candidate",
          files: [{ path: "src/value.txt", content: "wrong-value\n" }],
        },
      }),
    );
    await store.createProposal(fixtureProposal({ id: "prop-bbb-0001", baseCommit: repo.baseCommit }));

    const first = await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND });
    assert.equal(first.evaluated, 1);
    assert.equal(first.proposalId, "prop-aaa-0001");
    assert.equal(first.status, "failed");
    assert.equal((await store.getProposal("prop-bbb-0001")).status, "proposed");
    assert.equal((await store.getProposal("prop-bbb-0001")).attempts, 0);

    const second = await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND });
    assert.equal(second.evaluated, 1);
    assert.equal(second.proposalId, "prop-bbb-0001");
    assert.equal(second.outcome, "passed");
    assert.equal((await store.getProposal("prop-bbb-0001")).status, "awaiting_approval");

    assert.deepEqual(await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND }), {
      outcome: "idle",
      evaluated: 0,
    });
  });

  it("rejects a passed proposal without writing any code", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({ id: "prop-reject-0001", baseCommit: repo.baseCommit }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-reject-0001",
      testCommand: TEST_COMMAND,
    });
    assert.equal(evaluation.outcome, "passed");

    await expectRejects(
      rejectProposal({
        projectRoot: repo.dir,
        proposalId: "prop-reject-0001",
        decidedBy: "   ",
        reason: "not now",
      }),
      "E_RSI_BAD_APPROVAL",
    );
    const rejection = await rejectProposal({
      projectRoot: repo.dir,
      proposalId: "prop-reject-0001",
      decidedBy: "human-reviewer",
      reason: "hypothesis not worth it",
    });
    assert.equal(rejection.decision, "rejected");
    assert.equal(rejection.evaluationId, evaluation.id);
    const proposal = await store.getProposal("prop-reject-0001");
    assert.equal(proposal.status, "rejected");
    assert.equal(proposal.approvalId, rejection.id);
    const rollbackDir = rsiPaths(repo.dir).rollbackPointsDir;
    assert.equal(existsSync(rollbackDir) ? (await readdir(rollbackDir)).length : 0, 0);
    assert.equal(existsSync(join(repo.dir, "src", "value.txt")), false);
    assert.equal(await readFile(join(repo.dir, "skills", "sage-kit", "SKILL.md"), "utf8"), SKILL_MD);
  });
});

describe("M3 RSI durable evidence export", () => {
  it("exports a self-contained JSON summary for a finished evaluation", async () => {
    const repo = await writeFixtureRepo();
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({ id: "prop-export-0001", baseCommit: repo.baseCommit }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-export-0001",
      testCommand: TEST_COMMAND,
    });
    const exported = await exportEvaluationSummary({
      projectRoot: repo.dir,
      evaluationId: evaluation.id,
    });
    assert.ok(exported.filePath !== undefined);
    assert.equal(existsSync(exported.filePath), true);
    const parsed = JSON.parse(await readFile(exported.filePath, "utf8"));
    assert.equal(parsed.schemaVersion, RSI_SCHEMA_VERSION);
    assert.equal(parsed.proposal.id, "prop-export-0001");
    assert.equal(parsed.evaluation.id, evaluation.id);
    assert.equal(parsed.evaluation.outcome, "passed");
    assert.deepEqual(parsed.approvals, []);
    assert.equal("workspace" in parsed.evaluation, false);
    assert.ok(exported.filePath.endsWith(join("exports", `${evaluation.id}.json`)));

    const custom = await exportEvaluationSummary({
      projectRoot: repo.dir,
      evaluationId: evaluation.id,
      outFile: "reports/rsi-evidence.json",
    });
    assert.equal(custom.filePath, join(repo.dir, "reports", "rsi-evidence.json"));
    assert.ok(existsSync(custom.filePath));

    await expectRejects(
      exportEvaluationSummary({
        projectRoot: repo.dir,
        evaluationId: evaluation.id,
        outFile: "../escape.json",
      }),
      "E_RSI_UNSAFE_PATH",
    );
    const inMemory = await exportEvaluationSummary({
      projectRoot: repo.dir,
      evaluationId: evaluation.id,
      write: false,
    });
    assert.equal(inMemory.filePath, undefined);
    assert.equal(inMemory.summary.evaluation.id, evaluation.id);
  });
});

describe("M3 RSI optional control-plane record", () => {
  it("records task/run/event idempotently when the M2 control store is available", async () => {
    const repo = await writeFixtureRepo();
    const rsi = openRsi(repo.dir);
    await rsi.createProposal(
      fixtureProposal({ id: "prop-control-0001", baseCommit: repo.baseCommit }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-control-0001",
      testCommand: TEST_COMMAND,
    });
    const proposal = await rsi.getProposal("prop-control-0001");

    const control = openControl(repo.dir);
    cleanups.push(() => control.close());
    try {
      const first = recordEvaluationInControl({ store: control, proposal, evaluation });
      assert.equal(first.taskCreated, true);
      assert.equal(first.runCreated, true);
      assert.ok(first.eventId !== undefined);
      assert.match(first.taskId, /^rsi-task-[0-9a-f]{16}$/);
      assert.match(first.runId, /^rsi-run-[0-9a-f]{16}$/);

      const task = control.getTask(first.taskId);
      assert.equal(task.status, "review");
      assert.equal(task.source, "rsi");
      assert.equal(task.externalId, proposal.id);
      const run = control.getRun(first.runId);
      assert.equal(run.status, "exited");
      assert.equal(run.exitCode, 0);
      assert.deepEqual(run.command, TEST_COMMAND);
      assert.equal(run.host, "rsi-evaluator");
      const events = control.listEvents({ runId: first.runId });
      const recorded = events.filter((event) => event.type === "rsi.evaluation");
      assert.equal(recorded.length, 1);
      assert.equal(recorded[0].data.outcome, "passed");
      assert.equal(recorded[0].data.repeats, 1);
      assert.ok(events.some((event) => event.type === "run.started"));
      assert.ok(events.some((event) => event.type === "run.finished"));

      const again = recordEvaluationInControl({ store: control, proposal, evaluation });
      assert.equal(again.taskCreated, false);
      assert.equal(again.runCreated, false);
      assert.equal(again.taskId, first.taskId);
      assert.equal(again.runId, first.runId);
      assert.equal(control.listTasks().filter((item) => item.id === first.taskId).length, 1);
      assert.equal(control.listRuns({ taskId: first.taskId }).length, 1);
    } finally {
      control.close();
    }
  });

  it("records a failed evaluation as a failed control-plane run", async () => {
    const repo = await writeFixtureRepo();
    const rsi = openRsi(repo.dir);
    await rsi.createProposal(
      fixtureProposal({
        id: "prop-control-fail",
        baseCommit: repo.baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "failing candidate",
          files: [{ path: "src/value.txt", content: "wrong-value\n" }],
        },
      }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-control-fail",
      testCommand: TEST_COMMAND,
    });
    const proposal = await rsi.getProposal("prop-control-fail");
    const control = openControl(repo.dir);
    try {
      const record = recordEvaluationInControl({ store: control, proposal, evaluation });
      const run = control.getRun(record.runId);
      assert.equal(run.status, "failed");
      assert.equal(run.errorCode, "E_RSI_TESTS_FAILED");
      assert.notEqual(run.exitCode, 0);
      const events = control.listEvents({ runId: record.runId });
      const recorded = events.filter((event) => event.type === "rsi.evaluation");
      assert.equal(recorded.length, 1);
      assert.equal(recorded[0].data.outcome, "failed");
      assert.equal(recorded[0].data.reasonCode, "E_RSI_TESTS_FAILED");
    } finally {
      control.close();
    }
  });
});

describe("M3 RSI safety invariants", () => {
  it("never imports network modules, calls a model SDK or owns a timer", async () => {
    const files = (await readdir(join(REPO_ROOT, "src", "rsi"), { recursive: true })).filter((name) =>
      name.endsWith(".ts"),
    );
    assert.ok(files.length >= 10);
    const forbidden = [
      /from\s+["']node:(?:http|https|net|tls|dns|dgram)["']/,
      /from\s+["'](?:undici|axios|node-fetch|openai|@anthropic-ai\/sdk|@ai-sdk\/[^"']+)["']/,
      /\bfetch\s*\(/,
      /\bXMLHttpRequest\b/,
      /\bWebSocket\b/,
    ];
    for (const relative of files) {
      const source = await readFile(join(REPO_ROOT, "src", "rsi", relative), "utf8");
      for (const pattern of forbidden) {
        assert.doesNotMatch(source, pattern, `${relative} must not contain ${pattern}`);
      }
    }

    // `runOnce` is the only entry point and it owns no scheduler/auto-approval.
    const runSource = await readFile(join(REPO_ROOT, "src", "rsi", "run.ts"), "utf8");
    assert.doesNotMatch(runSource, /setInterval\s*\(/);
    assert.doesNotMatch(runSource, /\.approve\s*\(/);
    assert.doesNotMatch(runSource, /\.merge\s*\(|\.publish\s*\(/);

    // Approval always requires an explicit human decision token.
    const approveSource = await readFile(join(REPO_ROOT, "src", "rsi", "approve.ts"), "utf8");
    assert.match(approveSource, /approvalToken/);
    assert.match(approveSource, /decidedBy/);
  });

  it("F08: recovers an evaluating proposal with no completed evidence", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    const created = await store.createProposal(
      fixtureProposal({ id: "prop-interrupted-0001", baseCommit: repo.baseCommit }),
    );
    await store.saveProposal({
      ...created,
      status: "evaluating",
      attempts: 1,
      evaluationId: "eval-20260101000000-abc123",
      updatedAt: "2026-01-01T00:00:00.000Z",
    });

    const result = await runOnce({ projectRoot: repo.dir, testCommand: TEST_COMMAND });
    assert.equal(result.outcome, "idle");
    const after = await store.getProposal("prop-interrupted-0001");
    assert.equal(after.status, "failed");
    const evaluation = await store.getEvaluation("eval-20260101000000-abc123");
    assert.equal(evaluation.complete, true);
    assert.equal(evaluation.reasonCode, "E_RSI_INTERRUPTED");
    assert.equal(evaluation.runs.length, 0);
  });

  it("F08b: recovery cannot race an evaluator that holds the lock", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    const created = await store.createProposal(
      fixtureProposal({ id: "prop-locked-0001", baseCommit: repo.baseCommit }),
    );
    await store.saveProposal({
      ...created,
      status: "evaluating",
      attempts: 1,
      evaluationId: "eval-20260101000000-locked",
      updatedAt: "2026-01-01T00:00:00.000Z",
    });
    const lock = await acquireEvaluationLock(store);
    try {
      // The recovery path must take the same lock, not merely inspect it, so a
      // live evaluator's completed evidence cannot be overwritten.
      assert.deepEqual(await recoverInterruptedEvaluations(store), []);
      assert.equal((await store.getProposal("prop-locked-0001")).status, "evaluating");
    } finally {
      await lock.release();
    }
    // Once the evaluator is gone, the stale evaluating proposal is recoverable.
    const recovered = await recoverInterruptedEvaluations(store);
    assert.equal(recovered.length, 1);
    assert.equal((await store.getProposal("prop-locked-0001")).status, "failed");
  });

  it("F08c: concurrent lock acquisition has exactly one owner", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    await mkdir(store.paths.lockPath.replace(/[\\/][^\\/]+$/, ""), { recursive: true });
    await writeFile(
      store.paths.lockPath,
      JSON.stringify({ pid: 999999, owner: "stale-owner", startedAt: "2026-01-01T00:00:00.000Z" }),
      "utf8",
    );
    const results = await Promise.all(
      Array.from({ length: 8 }, () =>
        acquireEvaluationLock(store).then(
          (lock) => ({ ok: true, lock }),
          (error) => ({ ok: false, code: error.code }),
        ),
      ),
    );
    const winners = results.filter((result) => result.ok);
    assert.equal(winners.length, 1, "only one concurrent stale-lock takeover may succeed");
    assert.equal(results.filter((result) => !result.ok).length, 7);
    await winners[0].lock.release();
  });

  it("F08d: an old mutex owned by a live process is not stolen", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    const mutex = `${store.paths.lockPath}.mutex`;
    await mkdir(dirname(mutex), { recursive: true });
    await mkdir(mutex, { recursive: true });
    await writeFile(join(mutex, "owner"), JSON.stringify({ pid: process.pid }), "utf8");
    const old = new Date(Date.now() - 60_000);
    await utimes(mutex, old, old);
    await assert.rejects(
      () => acquireEvaluationLock(store),
      (error) => error.code === "E_RSI_LOCK_FAILED",
      "a live owner must never be evicted by mutex age alone",
    );
    await rm(mutex, { recursive: true, force: true });
  });

  it("F08e: a stale mutex fails closed instead of being moved", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    const mutex = `${store.paths.lockPath}.mutex`;
    await mkdir(dirname(mutex), { recursive: true });
    await mkdir(mutex, { recursive: true });
    await writeFile(join(mutex, "owner"), JSON.stringify({ pid: 999999, owner: "stale-owner" }), "utf8");
    const before = await access(mutex).then(
      () => true,
      () => false,
    );
    assert.equal(before, true);
    await assert.rejects(
      () => acquireEvaluationLock(store),
      (error) => error.code === "E_RSI_LOCK_STALE",
      "an identity-ambiguous mutex must not be moved automatically",
    );
    assert.equal(
      await access(mutex).then(
        () => true,
        () => false,
      ),
      true,
      "the stale mutex must remain for explicit cleanup",
    );
    await rm(mutex, { recursive: true, force: true });
    const lock = await acquireEvaluationLock(store);
    await lock.release();
  });

  it("F08f: release does not starve under in-process acquire churn", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    const cycles = 25;
    const results = await Promise.all(
      Array.from({ length: 8 }, async () => {
        let completed = 0;
        while (completed < cycles) {
          let lock;
          try {
            lock = await acquireEvaluationLock(store);
          } catch (error) {
            if (error.code === "E_RSI_EVALUATION_LOCKED") {
              await new Promise((resolvePromise) => setTimeout(resolvePromise, 1));
              continue;
            }
            throw error;
          }
          await new Promise((resolvePromise) => setTimeout(resolvePromise, 1));
          await lock.release();
          completed += 1;
        }
        return completed;
      }),
    );
    assert.deepEqual(results, Array(8).fill(cycles));
    assert.equal(
      await access(store.paths.lockPath).then(
        () => true,
        () => false,
      ),
      false,
      "no evaluation lock may remain after all cycles",
    );
    assert.equal(
      await access(`${store.paths.lockPath}.mutex`).then(
        () => true,
        () => false,
      ),
      false,
      "no mutex may remain after all cycles",
    );
  });

  it("F02: rejects a candidate that writes through a repository symlink", async () => {
    if (process.platform === "win32") return;
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const target = join(repo.dir, "tests", "check.test.mjs");
    const before = await readFile(target, "utf8");
    await symlink(target, join(repo.dir, "escape-link"), "file");
    git(repo.dir, ["add", "-A"]);
    git(repo.dir, ["commit", "-q", "-m", "add escape symlink"]);
    const baseCommit = git(repo.dir, ["rev-parse", "HEAD"]);
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-symlink-0001",
        baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "must not follow the symlink",
          files: [{ path: "escape-link", content: "pwned\n" }],
        },
      }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-symlink-0001",
      testCommand: TEST_COMMAND,
    });
    assert.equal(evaluation.outcome, "failed");
    assert.equal(await readFile(target, "utf8"), before);
    const after = await store.getProposal("prop-symlink-0001");
    assert.equal(after.status, "failed");
  });

  it("F02: treats protected paths case-insensitively", async () => {
    const repo = await writeFixtureRepo({ baselinePasses: true });
    const store = openRsi(repo.dir);
    await store.createProposal(
      fixtureProposal({
        id: "prop-case-0001",
        baseCommit: repo.baseCommit,
        candidate: {
          builder: "fixture-builder",
          summary: "case bypass attempt",
          files: [{ path: "TESTS/check.test.mjs", content: "ignored\n" }],
        },
      }),
    );
    const evaluation = await evaluateCandidate({
      projectRoot: repo.dir,
      proposalId: "prop-case-0001",
      testCommand: TEST_COMMAND,
    });
    assert.equal(evaluation.outcome, "failed");
    assert.equal(evaluation.reasonCode, "E_RSI_PROTECTED_ASSET");
  });

  it("documents that evaluation requires local git and never fetches", async () => {
    const worktreeSource = await readFile(join(REPO_ROOT, "src", "rsi", "worktree.ts"), "utf8");
    assert.match(worktreeSource, /git worktree/);
    assert.match(worktreeSource, /no fetch/);
    assert.doesNotMatch(worktreeSource, /\["fetch"|\["pull"/);

    // The evaluator rejects a non-repository before it can run anything.
    const clone = await tempProject();
    const store = openRsi(clone);
    await writeFixtureFiles(clone);
    await store.createProposal(fixtureProposal({ id: "prop-nogit-0001" }));
    await assert.rejects(
      evaluateCandidate({
        projectRoot: clone,
        proposalId: "prop-nogit-0001",
        testCommand: TEST_COMMAND,
      }),
      (error) => error.code === "E_RSI_NOT_GIT_REPO",
    );
  });
});
