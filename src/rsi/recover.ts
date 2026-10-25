/**
 * Crash recovery for manual RSI evaluations.
 *
 * The evaluator writes a draft evaluation and the proposal's `evaluationId`
 * before running commands. A crash therefore leaves either a readable draft or
 * a completed evaluation whose proposal status was not updated. Recovery only
 * runs when no live evaluation lock exists; it never retries a candidate and
 * never approves anything.
 */
import { acquireEvaluationLock } from "./lock.js";
import { newRsiId } from "./paths.js";
import type { RsiStore } from "./store.js";
import { RSI_SCHEMA_VERSION, type Evaluation, type Proposal } from "./types.js";
import { SageError } from "../core/errors.js";

const EMPTY_LOG = { stdout: "", stderr: "", truncated: false };

function interruptedEvaluation(store: RsiStore, proposal: Proposal, evaluationId: string, finishedAt: string): Evaluation {
  return {
    schemaVersion: RSI_SCHEMA_VERSION,
    id: evaluationId,
    proposalId: proposal.id,
    attempt: proposal.attempts,
    complete: true,
    startedAt: proposal.updatedAt,
    finishedAt,
    baseCommit: proposal.baseCommit,
    repeats: 1,
    command: [],
    outcome: "failed",
    reasonCode: "E_RSI_INTERRUPTED",
    reasonMessage: "Evaluation process ended before a complete evidence record was written.",
    ranTests: false,
    exitCode: null,
    signal: null,
    timedOut: false,
    durationMs: 0,
    diff: { files: 0, changedLines: 0, limits: { maxFiles: 0, maxChangedLines: 0 } },
    protectedAssets: { paths: [], ok: true, changed: [] },
    log: EMPTY_LOG,
    runs: [],
    baseline: { runs: [], passedRuns: 0, failedRuns: 0, outcome: "not_run" },
    comparison: {
      candidateRuns: 0,
      baselineRuns: 0,
      candidatePassedRuns: 0,
      baselinePassedRuns: 0,
      noWeakerThanBaseline: false,
    },
  };
}

/**
 * Recover `evaluating` proposals left by a dead process. Returns the proposals
 * that were changed. Recovery holds the same evaluation lock as the evaluator
 * for the whole read/repair window, so an evaluator that starts after the lock
 * check cannot race the writes. If another evaluator is already alive, this is
 * a no-op.
 */
export async function recoverInterruptedEvaluations(store: RsiStore): Promise<Proposal[]> {
  let lock;
  try {
    lock = await acquireEvaluationLock(store);
  } catch (error) {
    if (error instanceof SageError && error.code === "E_RSI_EVALUATION_LOCKED") return [];
    throw error;
  }
  let primary: unknown;
  try {
    const recovered: Proposal[] = [];
    for (const proposal of await store.listProposals({ status: "evaluating" })) {
      const now = store.nowIso();
      let evaluationId = proposal.evaluationId;
      let evaluation: Evaluation | undefined;
      if (evaluationId !== undefined) {
        try {
          evaluation = await store.getEvaluation(evaluationId);
        } catch (error) {
          // Only a genuinely missing record may be synthesized. Treating a
          // read error (EIO, permission, corrupt JSON) as "missing" would
          // overwrite a completed successful evaluation with a failure.
          if (error instanceof SageError && error.code === "E_RSI_NOT_FOUND") {
            evaluation = undefined;
          } else {
            throw error;
          }
        }
      }
      if (evaluation === undefined) {
        evaluationId = evaluationId ?? newRsiId("eval", now);
        evaluation = interruptedEvaluation(store, proposal, evaluationId, now);
        await store.saveEvaluation(evaluation);
      } else if (evaluation.complete === false) {
        evaluation = {
          ...evaluation,
          complete: true,
          outcome: "failed",
          reasonCode: "E_RSI_INTERRUPTED",
          reasonMessage: "Evaluation process ended before a complete evidence record was written.",
          finishedAt: now,
        };
        await store.saveEvaluation(evaluation);
      }
      const nextStatus = evaluation.outcome === "passed" ? "awaiting_approval" : "failed";
      const next: Proposal = {
        ...proposal,
        status: nextStatus,
        evaluationId,
        updatedAt: now,
      };
      await store.saveProposal(next);
      recovered.push(next);
    }
    return recovered;
  } catch (error) {
    primary = error;
    throw error;
  } finally {
    try {
      await lock.release();
    } catch (releaseError) {
      if (primary !== undefined) {
        throw new AggregateError(
          [primary as Error, releaseError as Error],
          "RSI recovery failed and its lock could not be released",
        );
      }
      throw releaseError;
    }
  }
}
