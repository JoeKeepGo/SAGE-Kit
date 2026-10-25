/**
 * `runOnce` — one manually triggered improvement step.
 *
 * There is deliberately no timer, daemon, queue or default scheduler (docs §9,
 * D-011): nothing happens until a caller invokes `runOnce`. One call picks the
 * oldest `proposed` proposal, evaluates exactly one candidate and stops. It can
 * reach `awaiting_approval` but never approves, merges, publishes or rewrites
 * `SKILL.md`; a human must decide.
 */
import { evaluateCandidate } from "./evaluate.js";
import { recoverInterruptedEvaluations } from "./recover.js";
import { resolveRsiStore, type RsiStore } from "./store.js";
import type { RsiLimits, RunOnceResult } from "./types.js";

export interface RunOnceOptions {
  /** Project root; optional when a `store` is passed. Must be the git repo root. */
  projectRoot?: string;
  store?: RsiStore;
  /** Fixed evaluator suite; see `EvaluateCandidateOptions.testCommand`. */
  testCommand: readonly string[];
  /** Number of baseline/candidate runs; default 1, bounded by `limits.maxRepeats`. */
  repeats?: number;
  limits?: Partial<RsiLimits>;
  protectedPaths?: readonly string[];
}

export async function runOnce(options: RunOnceOptions): Promise<RunOnceResult> {
  const store = resolveRsiStore(options);
  // A crashed evaluation is marked interrupted before another candidate starts;
  // it is never retried automatically.
  await recoverInterruptedEvaluations(store);
  const proposed = await store.listProposals({ status: "proposed" });
  const first = proposed[0];
  if (first === undefined) {
    return { outcome: "idle", evaluated: 0 };
  }
  const evaluation = await evaluateCandidate({
    store,
    proposalId: first.id,
    testCommand: options.testCommand,
    ...(options.repeats === undefined ? {} : { repeats: options.repeats }),
    ...(options.limits === undefined ? {} : { limits: options.limits }),
    ...(options.protectedPaths === undefined ? {} : { protectedPaths: options.protectedPaths }),
  });
  const after = await store.getProposal(first.id);
  const result: RunOnceResult = {
    outcome: evaluation.outcome,
    evaluated: 1,
    proposalId: first.id,
    evaluationId: evaluation.id,
    status: after.status,
  };
  if (evaluation.reasonCode !== undefined) result.reasonCode = evaluation.reasonCode;
  return result;
}
