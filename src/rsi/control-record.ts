/**
 * Optional control-plane recording for RSI evaluations.
 *
 * M2 provides SQLite tasks/runs/events/leases behind `openControl()`. Recording
 * an evaluation there is an explicit, opt-in audit step: the file-mode RSI
 * store remains the single authoritative writer for RSI state (D-005), this
 * function is never called automatically by `runOnce`/`evaluateCandidate` and
 * the caller must pass an already-open `ControlStore`.
 *
 * What is recorded (idempotent by deterministic ids/idempotency keys):
 *   - one `review` task for the proposal (source `rsi`);
 *   - one finished run per evaluation (host `rsi-evaluator`, the fixed command,
 *     exit code and failure code/message);
 *   - one `rsi.evaluation` event with compact compare/repeat evidence.
 *
 * No approval/merge/publish is recorded or performed here.
 */
import type { ControlStore } from "../control/index.js";
import { SageError } from "../core/errors.js";
import { sha256 } from "../core/fs-utils.js";
import type { Evaluation, Proposal } from "./types.js";

export interface RecordEvaluationInControlOptions {
  /** An already-open M2 control store (`openControl(projectRoot)`). */
  store: ControlStore;
  proposal: Proposal;
  evaluation: Evaluation;
}

export interface EvaluationControlRecord {
  taskId: string;
  runId: string;
  taskCreated: boolean;
  runCreated: boolean;
  /** Event id when this call recorded `rsi.evaluation`. */
  eventId?: string;
}

function isMissing(error: unknown): boolean {
  return (
    error instanceof SageError &&
    (error.code === "E_TASK_NOT_FOUND" || error.code === "E_RUN_NOT_FOUND")
  );
}

/** Deterministic control-plane id: `rsi-task-<16 hex>` (same proposal, same id). */
function controlId(prefix: string, value: string): string {
  return `${prefix}-${sha256(value).slice(0, 16)}`;
}

/**
 * Record one evaluation as a task/run/event in the optional control plane.
 * Safe to call twice for the same evaluation: the second call reuses the task,
 * run and event instead of duplicating them.
 */
export function recordEvaluationInControl(
  options: RecordEvaluationInControlOptions,
): EvaluationControlRecord {
  const { store, proposal, evaluation } = options;
  const taskId = controlId("rsi-task", proposal.id);
  const runId = controlId("rsi-run", evaluation.id);

  const existingTask = (() => {
    try {
      return store.getTask(taskId);
    } catch (error) {
      if (!isMissing(error)) throw error;
      return undefined;
    }
  })();
  const task =
    existingTask ??
    store.createTask({
      id: taskId,
      title: `RSI evaluation ${proposal.id}`,
      description: `RSI evaluation evidence for ${proposal.id}: ${proposal.hypothesis}`.slice(0, 2_000),
      status: "review",
      acceptance: [
        "every candidate run passes the fixed evaluator command",
        "no protected evaluation asset changed",
        "candidate is not weaker than the base-commit baseline",
        "human approval is recorded separately under .sage-kit/rsi/",
      ],
      source: "rsi",
      externalId: proposal.id,
      ...(proposal.feedbackRefs[0]?.url === undefined ? {} : { externalUrl: proposal.feedbackRefs[0].url }),
      idempotencyKey: `rsi:proposal:${proposal.id}`,
    });

  const existingRun = (() => {
    try {
      return store.getRun(runId);
    } catch (error) {
      if (!isMissing(error)) throw error;
      return undefined;
    }
  })();

  if (existingRun !== undefined) {
    return {
      taskId: task.id,
      runId: existingRun.id,
      taskCreated: existingTask === undefined,
      runCreated: false,
    };
  }

  store.recordRun({
    id: runId,
    taskId: task.id,
    host: "rsi-evaluator",
    command: evaluation.command,
    startedAt: evaluation.startedAt,
    idempotencyKey: `rsi:evaluation:${evaluation.id}`,
  });
  const failed = evaluation.outcome !== "passed";
  store.finishRun(runId, {
    status: failed ? "failed" : "exited",
    exitCode: evaluation.exitCode,
    ...(failed
      ? {
          errorCode: evaluation.reasonCode ?? "E_RSI_EVALUATION_FAILED",
          ...(evaluation.reasonMessage === undefined ? {} : { errorMessage: evaluation.reasonMessage }),
        }
      : {}),
    endedAt: evaluation.finishedAt,
  });
  const data: Record<string, unknown> = {
    proposalId: proposal.id,
    evaluationId: evaluation.id,
    outcome: evaluation.outcome,
    repeats: evaluation.repeats,
    baselineOutcome: evaluation.baseline.outcome,
    candidatePassedRuns: evaluation.comparison.candidatePassedRuns,
    baselinePassedRuns: evaluation.comparison.baselinePassedRuns,
    noWeakerThanBaseline: evaluation.comparison.noWeakerThanBaseline,
  };
  if (evaluation.reasonCode !== undefined) data.reasonCode = evaluation.reasonCode;
  const event = store.appendEvent({
    type: "rsi.evaluation",
    taskId: task.id,
    runId,
    data,
    createdAt: evaluation.finishedAt,
  });
  return {
    taskId: task.id,
    runId,
    taskCreated: existingTask === undefined,
    runCreated: true,
    eventId: event.id,
  };
}
