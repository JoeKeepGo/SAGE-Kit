/**
 * Candidate evaluation — the Evaluator side of the Builder/Evaluator split.
 *
 * The evaluator:
 *   1. validates the proposal is `proposed` and the candidate is within budget;
 *   2. hashes the protected evaluation assets of the source tree;
 *   3. copies the project into an isolated temp workspace;
 *   4. applies the candidate there (never in the source tree);
 *   5. runs the *fixed* command supplied by the evaluator wiring (never by the
 *      proposal), with a hard timeout and captured, redacted log tails;
 *   6. verifies the protected assets did not change during the run;
 *   7. records a pass/fail evaluation and moves the proposal to
 *      `awaiting_approval` (pass) or `failed` (fail).
 *
 * It never approves, merges, publishes, rewrites `SKILL.md`, calls a model or
 * opens a network connection (the fixed command is whatever the caller wired).
 */
import { SageError } from "../core/errors.js";
import { truncateUtf8 } from "../core/fs-utils.js";
import {
  applyCandidateFiles,
  assessCandidate,
  diffProtectedManifests,
  hashProtectedAssets,
} from "./candidate.js";
import { acquireEvaluationLock } from "./lock.js";
import { newRsiId } from "./paths.js";
import { runFixedCommand, type FixedCommandResult } from "./process.js";
import { resolveRsiStore, type RsiStore } from "./store.js";
import {
  RSI_SCHEMA_VERSION,
  type Evaluation,
  type EvaluationLog,
  type Proposal,
  type RsiLimits,
} from "./types.js";
import { normalizeLimits, normalizeProtectedPaths, validateRsiId, validateTestCommand } from "./validate.js";
import { createEvaluationWorkspace } from "./workspace.js";

export interface EvaluateCandidateOptions {
  /** Project root; optional when a `store` is passed. */
  projectRoot?: string;
  store?: RsiStore;
  proposalId: string;
  /**
   * The fixed evaluation suite, e.g. `[process.execPath, "--test", "tests/check.test.mjs"]`.
   * Chosen by the evaluator wiring, never by a proposal or candidate.
   */
  testCommand: readonly string[];
  limits?: Partial<RsiLimits>;
  /** Overrides `DEFAULT_PROTECTED_PATHS` (D-012 assets). */
  protectedPaths?: readonly string[];
  /** Extra top-level directories to exclude from the isolated copy. */
  copyExclude?: readonly string[];
}

function resolveStore(options: { projectRoot?: string; store?: RsiStore }): RsiStore {
  return resolveRsiStore(options);
}

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
  if (result === undefined) return { stdout: "", stderr: "", truncated: false };
  const stdout = truncateUtf8(redactLog(result.stdout), maxLogBytes);
  const stderr = truncateUtf8(redactLog(result.stderr), maxLogBytes);
  return { stdout: stdout.text, stderr: stderr.text, truncated: stdout.truncated || stderr.truncated };
}

function shortMessage(message: string): string {
  return message.replace(/\s+/g, " ").trim().slice(0, 1_000);
}

interface FailureInfo {
  reasonCode: string;
  reasonMessage: string;
}

function classifyFailure(
  applyError: string | undefined,
  commandResult: FixedCommandResult | undefined,
  protectedCheckError: string | undefined,
  protectedChanged: readonly string[],
  limits: RsiLimits,
): FailureInfo | undefined {
  if (applyError !== undefined) {
    return { reasonCode: "E_RSI_CANDIDATE_APPLY_FAILED", reasonMessage: shortMessage(applyError) };
  }
  if (commandResult === undefined) {
    return { reasonCode: "E_RSI_EVALUATION_FAILED", reasonMessage: "fixed evaluation command did not start" };
  }
  if (commandResult.spawnError !== undefined) {
    return { reasonCode: "E_RSI_EVAL_SPAWN_FAILED", reasonMessage: shortMessage(commandResult.spawnError) };
  }
  if (commandResult.timedOut) {
    return {
      reasonCode: "E_RSI_EVAL_TIMEOUT",
      reasonMessage: `fixed evaluation command exceeded ${limits.evaluationTimeoutMs} ms`,
    };
  }
  if (protectedCheckError !== undefined) {
    return { reasonCode: "E_RSI_PROTECTED_ASSET_UNVERIFIED", reasonMessage: shortMessage(protectedCheckError) };
  }
  if (protectedChanged.length > 0) {
    return {
      reasonCode: "E_RSI_PROTECTED_ASSET_CHANGED",
      reasonMessage: `fixed suite modified protected assets: ${protectedChanged.slice(0, 20).join(", ")}`,
    };
  }
  if (commandResult.exitCode !== 0) {
    return {
      reasonCode: "E_RSI_TESTS_FAILED",
      reasonMessage: `fixed evaluation command exited with code ${String(commandResult.exitCode)}`,
    };
  }
  return undefined;
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

interface PreRunFailure {
  assessment: Awaited<ReturnType<typeof assessCandidate>>;
  protectedPaths: readonly string[];
}

/**
 * Evaluate exactly one candidate. Throws on invalid input or infrastructure
 * failure; candidate/test failures are persisted as a failed `Evaluation`
 * record and move the proposal to `failed` (never `approved`).
 */
export async function evaluateCandidate(options: EvaluateCandidateOptions): Promise<Evaluation> {
  const store = resolveStore(options);
  const proposalId = validateRsiId(options.proposalId, "proposalId");
  const testCommand = validateTestCommand(options.testCommand);
  const limits = normalizeLimits(options.limits);
  const protectedPaths = normalizeProtectedPaths(options.protectedPaths);

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
    const assessment = await assessCandidate(store.projectRoot, proposal.candidate, { protectedPaths, limits });
    const startedAt = store.nowIso();
    const evaluationId = newRsiId("eval", startedAt);
    const baseEvaluation = {
      schemaVersion: RSI_SCHEMA_VERSION as 1,
      id: evaluationId,
      proposalId,
      startedAt,
      command: testCommand,
      diff: {
        files: assessment.changedFiles,
        changedLines: assessment.changedLines,
        limits: { maxFiles: limits.maxCandidateFiles, maxChangedLines: limits.maxChangedLines },
      },
    };

    if (!assessment.ok) {
      // Candidate rejected before any workspace exists: record the budget or
      // protected-asset failure, mark the proposal failed and stop.
      const evaluating = await markEvaluating(store, proposal);
      const finishedAt = store.nowIso();
      const preRun: PreRunFailure = { assessment, protectedPaths };
      const evaluation: Evaluation = {
        ...baseEvaluation,
        attempt: evaluating.attempts,
        finishedAt,
        outcome: "failed",
        ...(preRun.assessment.reasonCode === undefined ? {} : { reasonCode: preRun.assessment.reasonCode }),
        ...(preRun.assessment.reasonMessage === undefined
          ? {}
          : { reasonMessage: preRun.assessment.reasonMessage }),
        ranTests: false,
        exitCode: null,
        signal: null,
        timedOut: false,
        durationMs: 0,
        protectedAssets: {
          paths: [...preRun.protectedPaths],
          ok: preRun.assessment.reasonCode !== "E_RSI_PROTECTED_ASSET",
          changed: [...preRun.assessment.protectedHits],
        },
        log: { stdout: "", stderr: "", truncated: false },
      };
      await store.saveEvaluation(evaluation);
      await store.saveProposal({ ...evaluating, status: "failed", evaluationId, updatedAt: finishedAt });
      return evaluation;
    }

    // Infrastructure prerequisites happen before the proposal leaves `proposed`
    // so a failure keeps it retryable; the workspace is removed on failure.
    const baselineManifest = await hashProtectedAssets(store.projectRoot, protectedPaths);
    const workspace = await createEvaluationWorkspace(store.projectRoot, { exclude: options.copyExclude });
    let evaluating: Proposal;
    try {
      evaluating = await markEvaluating(store, proposal);
    } catch (error) {
      await workspace.cleanup();
      throw error;
    }

    let commandResult: FixedCommandResult | undefined;
    let applyError: string | undefined;
    let protectedCheckError: string | undefined;
    let protectedChanged: string[] = [];
    let workspaceRemoved = false;
    try {
      try {
        await applyCandidateFiles(workspace.projectRoot, assessment.files);
      } catch (error) {
        applyError = (error as Error).message;
      }
      if (applyError === undefined) {
        commandResult = await runFixedCommand(testCommand, workspace.projectRoot, {
          timeoutMs: limits.evaluationTimeoutMs,
        });
        try {
          const afterManifest = await hashProtectedAssets(workspace.projectRoot, protectedPaths);
          protectedChanged = diffProtectedManifests(baselineManifest, afterManifest);
        } catch (error) {
          protectedCheckError = (error as Error).message;
        }
      }
    } finally {
      workspaceRemoved = await workspace.cleanup();
    }

    const failure = classifyFailure(applyError, commandResult, protectedCheckError, protectedChanged, limits);
    const finishedAt = store.nowIso();
    const evaluation: Evaluation = {
      ...baseEvaluation,
      attempt: evaluating.attempts,
      finishedAt,
      outcome: failure === undefined ? "passed" : "failed",
      ...(failure === undefined ? {} : { reasonCode: failure.reasonCode, reasonMessage: failure.reasonMessage }),
      ranTests: commandResult !== undefined,
      exitCode: commandResult?.exitCode ?? null,
      signal: commandResult?.signal ?? null,
      timedOut: commandResult?.timedOut ?? false,
      durationMs: commandResult?.durationMs ?? 0,
      protectedAssets: {
        paths: [...protectedPaths],
        ok: protectedCheckError === undefined && protectedChanged.length === 0,
        changed: protectedChanged,
      },
      log: summarizeLog(commandResult, limits.maxLogBytes),
      workspace: { kind: "temp-copy", tempDir: workspace.tempRoot, removed: workspaceRemoved },
    };
    await store.saveEvaluation(evaluation);
    await store.saveProposal({
      ...evaluating,
      status: failure === undefined ? "awaiting_approval" : "failed",
      evaluationId,
      updatedAt: finishedAt,
    });
    return evaluation;
  } finally {
    await lock.release();
  }
}
