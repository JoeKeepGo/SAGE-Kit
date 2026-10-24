/**
 * Candidate evaluation — the Evaluator side of the Builder/Evaluator split.
 *
 * M3b flow (docs/m3-rsi.md §5):
 *   1. validate the proposal is `proposed`, the git repo/commit exist and the
 *      candidate is within budget;
 *   2. create an isolated git worktree at the proposal's base commit and assess
 *      the candidate against that checkout (never against the main working
 *      tree);
 *   3. record baseline evidence: run the fixed command on the unmodified base
 *      commit `repeats` times, one fresh worktree per run;
 *   4. record candidate evidence: apply the candidate in a fresh worktree per
 *      run, run the same fixed command, re-check protected assets;
 *   5. candidate passes only when every candidate run passes, no protected
 *      asset changed, budgets hold, and it is not weaker than the baseline
 *      (candidate passed runs >= baseline passed runs);
 *   6. persist every run and move the proposal to `awaiting_approval` (pass) or
 *      `failed` (fail).
 *
 * There is no automatic retry: one call evaluates at most `repeats` bounded
 * runs of one candidate. It never approves, merges, publishes, rewrites
 * `SKILL.md`, calls a model or opens a network connection (the fixed command is
 * whatever the caller wired).
 */
import { SageError } from "../core/errors.js";
import { truncateUtf8 } from "../core/fs-utils.js";
import {
  applyCandidateFiles,
  assessCandidate,
  diffProtectedManifests,
  hashProtectedAssets,
  type ProtectedManifest,
} from "./candidate.js";
import { acquireEvaluationLock } from "./lock.js";
import { newRsiId } from "./paths.js";
import { runFixedCommand, type FixedCommandResult } from "./process.js";
import { resolveRsiStore, type RsiStore } from "./store.js";
import {
  RSI_SCHEMA_VERSION,
  type Evaluation,
  type EvaluationBaseline,
  type EvaluationComparison,
  type EvaluationLog,
  type EvaluationRun,
  type EvaluationRunKind,
  type EvaluationWorktree,
  type Proposal,
  type RsiLimits,
} from "./types.js";
import {
  normalizeLimits,
  normalizeProtectedPaths,
  normalizeRepeats,
  validateRsiId,
  validateTestCommand,
} from "./validate.js";
import {
  createEvaluationWorktree,
  resolveBaseCommit,
  resolveGitRepository,
  type GitWorktreeHandle,
} from "./worktree.js";

export interface EvaluateCandidateOptions {
  /** Project root; optional when a `store` is passed. Must be the git repo root. */
  projectRoot?: string;
  store?: RsiStore;
  proposalId: string;
  /**
   * The fixed evaluation suite, e.g. `[process.execPath, "--test", "tests/check.test.mjs"]`.
   * Chosen by the evaluator wiring, never by a proposal or candidate.
   */
  testCommand: readonly string[];
  /** Number of baseline/candidate runs; default 1, bounded by `limits.maxRepeats`. */
  repeats?: number;
  limits?: Partial<RsiLimits>;
  /** Overrides `DEFAULT_PROTECTED_PATHS` (D-012 assets). */
  protectedPaths?: readonly string[];
}

interface RunOptions {
  repoRoot: string;
  baseCommit: string;
  testCommand: readonly string[];
  protectedPaths: readonly string[];
  baselineManifest: ProtectedManifest;
  limits: RsiLimits;
}

interface FailureInfo {
  reasonCode: string;
  reasonMessage: string;
}

const EMPTY_LOG: EvaluationLog = { stdout: "", stderr: "", truncated: false };

const LOG_REDACTIONS: readonly [RegExp, string][] = [
  [/((?:password|passwd|token|secret|authorization|api[_-]?key)\s*[=:]\s*)([^\s,;]+)/gi, "$1[REDACTED]"],
  [/\b(sk-[A-Za-z0-9_-]{8,})\b/g, "[REDACTED]"],
];

/** Redact credential-looking values before a log tail is persisted (D-017). */
function redactLog(text: string): string {
  let redacted = text;
  for (const [pattern, replacement] of LOG_REDACTIONS) redacted = redacted.replace(pattern, replacement);
  return redacted;
}

function summarizeLog(result: FixedCommandResult | undefined, maxLogBytes: number): EvaluationLog {
  if (result === undefined) return EMPTY_LOG;
  const stdout = truncateUtf8(redactLog(result.stdout), maxLogBytes);
  const stderr = truncateUtf8(redactLog(result.stderr), maxLogBytes);
  return { stdout: stdout.text, stderr: stderr.text, truncated: stdout.truncated || stderr.truncated };
}

function shortMessage(message: string): string {
  return message.replace(/\s+/g, " ").trim().slice(0, 1_000);
}

function commandFailure(result: FixedCommandResult | undefined, limits: RsiLimits): FailureInfo | undefined {
  if (result === undefined) {
    return { reasonCode: "E_RSI_EVALUATION_FAILED", reasonMessage: "fixed evaluation command did not start" };
  }
  if (result.spawnError !== undefined) {
    return { reasonCode: "E_RSI_EVAL_SPAWN_FAILED", reasonMessage: shortMessage(result.spawnError) };
  }
  if (result.timedOut) {
    return {
      reasonCode: "E_RSI_EVAL_TIMEOUT",
      reasonMessage: `fixed evaluation command exceeded ${limits.evaluationTimeoutMs} ms`,
    };
  }
  if (result.exitCode !== 0) {
    return {
      reasonCode: "E_RSI_TESTS_FAILED",
      reasonMessage: `fixed evaluation command exited with code ${String(result.exitCode)}`,
    };
  }
  return undefined;
}

function candidateFailure(
  applyError: string | undefined,
  result: FixedCommandResult | undefined,
  protectedCheckError: string | undefined,
  protectedChanged: readonly string[],
  limits: RsiLimits,
): FailureInfo | undefined {
  if (applyError !== undefined) {
    return { reasonCode: "E_RSI_CANDIDATE_APPLY_FAILED", reasonMessage: shortMessage(applyError) };
  }
  const base = commandFailure(result, limits);
  if (base !== undefined) return base;
  if (protectedCheckError !== undefined) {
    return { reasonCode: "E_RSI_PROTECTED_ASSET_UNVERIFIED", reasonMessage: shortMessage(protectedCheckError) };
  }
  if (protectedChanged.length > 0) {
    return {
      reasonCode: "E_RSI_PROTECTED_ASSET_CHANGED",
      reasonMessage: `fixed suite modified protected assets: ${protectedChanged.slice(0, 20).join(", ")}`,
    };
  }
  return undefined;
}

function buildRun(input: {
  index: number;
  kind: EvaluationRunKind;
  worktree: EvaluationWorktree;
  applied: boolean;
  ranTests: boolean;
  result?: FixedCommandResult;
  failure?: FailureInfo;
  protectedPaths: readonly string[];
  protectedChanged: readonly string[];
  protectedCheckOk: boolean;
  limits: RsiLimits;
}): EvaluationRun {
  const run: EvaluationRun = {
    index: input.index,
    kind: input.kind,
    applied: input.applied,
    ranTests: input.ranTests,
    outcome: input.failure === undefined ? "passed" : "failed",
    exitCode: input.result?.exitCode ?? null,
    signal: input.result?.signal ?? null,
    timedOut: input.result?.timedOut ?? false,
    durationMs: input.result?.durationMs ?? 0,
    protectedAssets: {
      paths: [...input.protectedPaths],
      ok: input.protectedCheckOk && input.protectedChanged.length === 0,
      changed: [...input.protectedChanged],
    },
    log: summarizeLog(input.result, input.limits.maxLogBytes),
    worktree: input.worktree,
  };
  if (input.failure !== undefined) {
    run.reasonCode = input.failure.reasonCode;
    run.reasonMessage = input.failure.reasonMessage;
  }
  return run;
}

/**
 * Run the fixed command once in a fresh worktree. Baseline runs never apply a
 * candidate; candidate runs apply `candidateFiles` and compare protected assets
 * against the baseline manifest.
 */
async function runOne(
  options: RunOptions,
  kind: EvaluationRunKind,
  index: number,
  candidateFiles: Parameters<typeof applyCandidateFiles>[1],
): Promise<EvaluationRun> {
  let worktree: GitWorktreeHandle | undefined;
  let removed = true;
  try {
    try {
      worktree = await createEvaluationWorktree(options.repoRoot, options.baseCommit);
    } catch (error) {
      return buildRun({
        index,
        kind,
        worktree: { kind: "git-worktree", path: "", removed: true },
        applied: false,
        ranTests: false,
        failure: { reasonCode: "E_RSI_WORKTREE_FAILED", reasonMessage: shortMessage((error as Error).message) },
        protectedPaths: options.protectedPaths,
        protectedChanged: [],
        protectedCheckOk: true,
        limits: options.limits,
      });
    }

    let applied = true;
    let applyError: string | undefined;
    let result: FixedCommandResult | undefined;
    let protectedCheckError: string | undefined;
    let protectedChanged: string[] = [];
    try {
      if (kind === "candidate") {
        try {
          await applyCandidateFiles(worktree.path, candidateFiles);
        } catch (error) {
          applied = false;
          applyError = (error as Error).message;
        }
      }
      if (applied) {
        result = await runFixedCommand(options.testCommand, worktree.path, {
          timeoutMs: options.limits.evaluationTimeoutMs,
        });
        if (kind === "candidate") {
          try {
            const after = await hashProtectedAssets(worktree.path, options.protectedPaths);
            protectedChanged = diffProtectedManifests(options.baselineManifest, after);
          } catch (error) {
            protectedCheckError = (error as Error).message;
          }
        }
      }
    } finally {
      removed = await worktree.cleanup().catch(() => false);
    }

    const failure =
      kind === "candidate"
        ? candidateFailure(applyError, result, protectedCheckError, protectedChanged, options.limits)
        : commandFailure(result, options.limits);
    return buildRun({
      index,
      kind,
      worktree: { kind: "git-worktree", path: worktree.path, removed },
      applied,
      ranTests: result !== undefined,
      ...(result === undefined ? {} : { result }),
      ...(failure === undefined ? {} : { failure }),
      protectedPaths: options.protectedPaths,
      protectedChanged,
      protectedCheckOk: protectedCheckError === undefined,
      limits: options.limits,
    });
  } catch (error) {
    // Defensive: an unexpected plumbing error must not lose the evidence that
    // this run failed, and the worktree cleanup above still ran.
    return buildRun({
      index,
      kind,
      worktree: { kind: "git-worktree", path: worktree?.path ?? "", removed },
      applied: false,
      ranTests: false,
      failure: { reasonCode: "E_RSI_EVALUATION_FAILED", reasonMessage: shortMessage((error as Error).message) },
      protectedPaths: options.protectedPaths,
      protectedChanged: [],
      protectedCheckOk: true,
      limits: options.limits,
    });
  }
}

async function markEvaluating(store: RsiStore, proposal: Proposal): Promise<Proposal> {
  const next: Proposal = {
    ...proposal,
    status: "evaluating",
    attempts: proposal.attempts + 1,
    updatedAt: store.nowIso(),
  };
  await store.saveProposal(next);
  return next;
}

function emptyComparison(): EvaluationComparison {
  return {
    candidateRuns: 0,
    baselineRuns: 0,
    candidatePassedRuns: 0,
    baselinePassedRuns: 0,
    noWeakerThanBaseline: false,
  };
}

function mergeProtectedReports(
  protectedPaths: readonly string[],
  runs: readonly EvaluationRun[],
): { paths: string[]; ok: boolean; changed: string[] } {
  const changed = new Set<string>();
  for (const run of runs) {
    for (const path of run.protectedAssets.changed) changed.add(path);
  }
  return {
    paths: [...protectedPaths],
    ok: runs.every((run) => run.protectedAssets.ok),
    changed: [...changed].sort(),
  };
}

/**
 * Evaluate exactly one candidate. Throws on invalid input or git infrastructure
 * prerequisites (unknown commit, not a repo) before the proposal leaves
 * `proposed`, so the caller can fix the environment and retry. Candidate/test
 * failures are persisted as a failed `Evaluation` and move the proposal to
 * `failed`; only a pass reaches `awaiting_approval`.
 */
export async function evaluateCandidate(options: EvaluateCandidateOptions): Promise<Evaluation> {
  const store = resolveRsiStore(options);
  const proposalId = validateRsiId(options.proposalId, "proposalId");
  const testCommand = validateTestCommand(options.testCommand);
  const limits = normalizeLimits(options.limits);
  const protectedPaths = normalizeProtectedPaths(options.protectedPaths);
  const repeats = normalizeRepeats(options.repeats, limits);

  const lock = await acquireEvaluationLock(store);
  try {
    const proposal = await store.getProposal(proposalId);
    if (proposal.status !== "proposed") {
      throw new SageError(
        `Proposal ${proposalId} is ${proposal.status}; only proposed proposals can be evaluated`,
        "E_RSI_BAD_TRANSITION",
        1,
      );
    }

    // Infrastructure prerequisites: a git repo and a locally available base
    // commit. These throw before `evaluating`, so a missing commit is fixable
    // and does not burn the proposal's single attempt.
    const repoRoot = await resolveGitRepository(store.projectRoot);
    const baseCommit = await resolveBaseCommit(repoRoot, proposal.baseCommit);
    const startedAt = store.nowIso();
    const evaluationId = newRsiId("eval", startedAt);

    // Assess the candidate against a checkout of the base commit, not against
    // the main working tree (which may contain uncommitted changes).
    const assessmentWorktree = await createEvaluationWorktree(repoRoot, baseCommit);
    let assessment: Awaited<ReturnType<typeof assessCandidate>>;
    let baselineManifest: ProtectedManifest;
    try {
      assessment = await assessCandidate(assessmentWorktree.path, proposal.candidate, { protectedPaths, limits });
      baselineManifest = await hashProtectedAssets(assessmentWorktree.path, protectedPaths);
    } finally {
      await assessmentWorktree.cleanup().catch(() => false);
    }

    const diff = {
      files: assessment.changedFiles,
      changedLines: assessment.changedLines,
      limits: { maxFiles: limits.maxCandidateFiles, maxChangedLines: limits.maxChangedLines },
    };

    if (!assessment.ok) {
      // Rejected before any run: no baseline/candidate evidence exists.
      const evaluating = await markEvaluating(store, proposal);
      const finishedAt = store.nowIso();
      const evaluation: Evaluation = {
        schemaVersion: RSI_SCHEMA_VERSION,
        id: evaluationId,
        proposalId,
        attempt: evaluating.attempts,
        startedAt,
        finishedAt,
        baseCommit,
        repeats,
        command: testCommand,
        outcome: "failed",
        ...(assessment.reasonCode === undefined ? {} : { reasonCode: assessment.reasonCode }),
        ...(assessment.reasonMessage === undefined ? {} : { reasonMessage: assessment.reasonMessage }),
        ranTests: false,
        exitCode: null,
        signal: null,
        timedOut: false,
        durationMs: 0,
        diff,
        protectedAssets: {
          paths: [...protectedPaths],
          ok: assessment.reasonCode !== "E_RSI_PROTECTED_ASSET",
          changed: [...assessment.protectedHits],
        },
        log: EMPTY_LOG,
        runs: [],
        baseline: { runs: [], passedRuns: 0, failedRuns: 0, outcome: "not_run" },
        comparison: emptyComparison(),
      };
      await store.saveEvaluation(evaluation);
      await store.saveProposal({ ...evaluating, status: "failed", evaluationId, updatedAt: finishedAt });
      return evaluation;
    }

    const evaluating = await markEvaluating(store, proposal);
    const runOptions: RunOptions = {
      repoRoot,
      baseCommit,
      testCommand,
      protectedPaths,
      baselineManifest,
      limits,
    };

    const baselineRuns: EvaluationRun[] = [];
    for (let index = 1; index <= repeats; index += 1) {
      baselineRuns.push(await runOne(runOptions, "baseline", index, []));
    }
    const candidateRuns: EvaluationRun[] = [];
    for (let index = 1; index <= repeats; index += 1) {
      candidateRuns.push(await runOne(runOptions, "candidate", index, assessment.files));
    }

    const candidatePassedRuns = candidateRuns.filter((run) => run.outcome === "passed").length;
    const baselinePassedRuns = baselineRuns.filter((run) => run.outcome === "passed").length;
    const allCandidateRunsPassed = candidateRuns.length === repeats && candidatePassedRuns === repeats;
    const noWeakerThanBaseline = candidatePassedRuns >= baselinePassedRuns;
    const passed = allCandidateRunsPassed && noWeakerThanBaseline;
    const firstFailure = candidateRuns.find((run) => run.outcome === "failed");
    const failure: FailureInfo | undefined = passed
      ? undefined
      : firstFailure !== undefined
        ? {
            reasonCode: firstFailure.reasonCode ?? "E_RSI_TESTS_FAILED",
            reasonMessage: firstFailure.reasonMessage ?? "a candidate run failed",
          }
        : { reasonCode: "E_RSI_WEAKER_THAN_BASELINE", reasonMessage: "candidate did not pass all runs" };

    const baselineOutcome: EvaluationBaseline["outcome"] =
      baselineRuns.length === 0 ? "not_run" : baselinePassedRuns === repeats ? "passed" : "failed";
    const finishedAt = store.nowIso();
    const evaluation: Evaluation = {
      schemaVersion: RSI_SCHEMA_VERSION,
      id: evaluationId,
      proposalId,
      attempt: evaluating.attempts,
      startedAt,
      finishedAt,
      baseCommit,
      repeats,
      command: testCommand,
      outcome: passed ? "passed" : "failed",
      ...(failure === undefined ? {} : { reasonCode: failure.reasonCode, reasonMessage: failure.reasonMessage }),
      ranTests: candidateRuns.some((run) => run.ranTests),
      exitCode: candidateRuns[0]?.exitCode ?? null,
      signal: candidateRuns[0]?.signal ?? null,
      timedOut: candidateRuns.some((run) => run.timedOut),
      durationMs: candidateRuns.reduce((total, run) => total + run.durationMs, 0),
      diff,
      protectedAssets: mergeProtectedReports(protectedPaths, candidateRuns),
      log: candidateRuns[0]?.log ?? EMPTY_LOG,
      runs: candidateRuns,
      baseline: {
        runs: baselineRuns,
        passedRuns: baselinePassedRuns,
        failedRuns: baselineRuns.length - baselinePassedRuns,
        outcome: baselineOutcome,
      },
      comparison: {
        candidateRuns: candidateRuns.length,
        baselineRuns: baselineRuns.length,
        candidatePassedRuns,
        baselinePassedRuns,
        noWeakerThanBaseline,
      },
    };
    await store.saveEvaluation(evaluation);
    await store.saveProposal({
      ...evaluating,
      status: passed ? "awaiting_approval" : "failed",
      evaluationId,
      updatedAt: finishedAt,
    });
    return evaluation;
  } finally {
    await lock.release();
  }
}
