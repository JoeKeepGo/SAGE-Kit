/**
 * Read-only RSI release gate.
 *
 * A core task may reference an M3 proposal (`Task.rsiProposalId`). Before a
 * release/deploy action, a caller can ask this gate whether the referenced
 * proposal is genuinely "approved with passed evaluation evidence". The gate
 * only reads the file-mode RSI store; it never writes, re-evaluates, approves,
 * merges, publishes or rewrites `SKILL.md`.
 *
 * Conditions (all must hold):
 *   1. the proposal record exists and is readable;
 *   2. `proposal.status === "approved"`;
 *   3. `proposal.evaluationId` exists and that evaluation record reads back
 *      with `outcome === "passed"` and the same `proposalId`;
 *   4. `proposal.approvalId` exists and that approval record reads back with
 *      `decision === "approved"` and `proposalId === proposal.id`.
 *
 * Missing/corrupt records are reported as `ok: false` with a stable reason
 * string instead of throwing; unexpected I/O errors still surface. This keeps
 * "no approval evidence" a normal, auditable outcome rather than a crash.
 */
import { SageError } from "../core/errors.js";
import { openRsi } from "./store.js";
import type { Approval, Evaluation, Proposal } from "./types.js";

/** Result of `checkRsiGate()`; always safe to serialize. */
export interface RsiGateResult {
  ok: boolean;
  /**
   * Stable machine code, e.g. `"ok"`, `"proposal-not-found"`,
   * `"proposal-not-approved"`, `"evaluation-missing"`,
   * `"evaluation-not-passed"`, `"approval-missing"`,
   * `"approval-not-approved"`, `"proposal-unreadable"`.
   */
  reason: string;
  proposalId: string;
  /** Proposal status when the proposal record was readable. */
  status?: string;
}

/**
 * Same shape as `RSI_ID_PATTERN` in `src/rsi/validate.ts`. Duplicated on
 * purpose: the gate only needs to decide whether the id can be looked up, and
 * core callers must not depend on the RSI layer for validation.
 */
const RSI_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;

type Loaded<T> = { value: T; error?: undefined } | { value?: undefined; error: "missing" | "corrupt" };

/** Map store `SageError`s to a non-throwing load outcome. */
async function loadRecord<T>(read: () => Promise<T>): Promise<Loaded<T>> {
  try {
    return { value: await read() };
  } catch (error) {
    if (error instanceof SageError) {
      if (error.code === "E_RSI_NOT_FOUND") return { error: "missing" };
      if (error.code === "E_RSI_STORE_CORRUPT" || error.code === "E_RSI_BAD_ID") {
        return { error: "corrupt" };
      }
    }
    throw error;
  }
}

function failed(proposalId: string, reason: string, status?: string): RsiGateResult {
  return { ok: false, reason, proposalId, ...(status === undefined ? {} : { status }) };
}

/**
 * Check whether `proposalId` is an approved, human-approved, passing
 * proposal for `projectRoot`. Read-only; safe to call on a missing project
 * (directory reads return "missing").
 */
export async function checkRsiGate(projectRoot: string, proposalId: string): Promise<RsiGateResult> {
  const requested = typeof proposalId === "string" ? proposalId : String(proposalId);
  if (typeof proposalId !== "string" || !RSI_ID_PATTERN.test(proposalId)) {
    return failed(requested, "invalid-proposal-id");
  }

  const store = openRsi(projectRoot);
  const proposalRead = await loadRecord<Proposal>(() => store.getProposal(proposalId));
  if (proposalRead.error !== undefined) {
    return failed(proposalId, proposalRead.error === "missing" ? "proposal-not-found" : "proposal-unreadable");
  }
  const proposal = proposalRead.value;
  const status = proposal.status;

  if (status !== "approved") return failed(proposalId, "proposal-not-approved", status);

  const evaluationId = proposal.evaluationId;
  if (evaluationId === undefined) return failed(proposalId, "evaluation-missing", status);
  const evaluationRead = await loadRecord<Evaluation>(() => store.getEvaluation(evaluationId));
  if (evaluationRead.error !== undefined) {
    return failed(proposalId, evaluationRead.error === "missing" ? "evaluation-missing" : "evaluation-unreadable", status);
  }
  const evaluation = evaluationRead.value;
  if (evaluation.proposalId !== proposalId) {
    return failed(proposalId, "evaluation-mismatch", status);
  }
  if (evaluation.outcome !== "passed") {
    return failed(proposalId, "evaluation-not-passed", status);
  }

  const approvalId = proposal.approvalId;
  if (approvalId === undefined) return failed(proposalId, "approval-missing", status);
  const approvalRead = await loadRecord<Approval>(() => store.getApproval(approvalId));
  if (approvalRead.error !== undefined) {
    return failed(proposalId, approvalRead.error === "missing" ? "approval-missing" : "approval-unreadable", status);
  }
  const approval = approvalRead.value;
  if (approval.decision !== "approved") {
    return failed(proposalId, "approval-not-approved", status);
  }
  if (approval.proposalId !== proposalId) {
    return failed(proposalId, "approval-mismatch", status);
  }
  // The human decision must name the exact evaluation it approved. Without
  // this binding, a passing evaluation A could be paired with an approval that
  // references a different (or no) evaluation.
  if (approval.evaluationId !== evaluation.id) {
    return failed(proposalId, "approval-evaluation-mismatch", status);
  }

  return { ok: true, reason: "ok", proposalId, status };
}
