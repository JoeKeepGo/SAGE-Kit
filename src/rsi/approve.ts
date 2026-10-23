/**
 * Human approval gate and rollback points.
 *
 * An approval is a *deliberate* action, not "no objection": it requires a
 * one-time token returned by `requestApproval`, an explicit human identity
 * (`decidedBy`) and an existing rollback point for the proposal's base commit.
 * The token is persisted only as a sha256 hash.
 *
 * The skeleton never executes the rollback or publishes anything; it records
 * the rollback command and leaves execution to a human (D-011).
 */
import { randomBytes, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { SageError } from "../core/errors.js";
import { isPathInside, sha256 } from "../core/fs-utils.js";
import { newRsiId } from "./paths.js";
import { resolveRsiStore, type RsiStore } from "./store.js";
import {
  DEFAULT_APPROVAL_TTL_MS,
  RSI_SCHEMA_VERSION,
  type Approval,
  type Proposal,
  type RollbackPoint,
} from "./types.js";
import {
  cleanText,
  optionalCleanText,
  validateBaseCommit,
  validateBaseVersion,
  validateRsiId,
} from "./validate.js";

interface StoreOptions {
  projectRoot?: string;
  store?: RsiStore;
}

function requireApprovalToken(value: unknown): string {
  if (typeof value !== "string" || !/^[0-9a-f]{32}$/.test(value)) {
    throw new SageError("approvalToken must be the 32-char hex token returned by request-approval", "E_RSI_BAD_APPROVAL", 2);
  }
  return value;
}

function tokenHashMatches(token: string, expectedHash: string): boolean {
  const actual = Buffer.from(sha256(token), "hex");
  const expected = Buffer.from(expectedHash, "hex");
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

function approvalExpired(expiresAt: string, nowIso: string): boolean {
  const expires = Date.parse(expiresAt);
  if (!Number.isFinite(expires)) {
    throw new SageError(`Corrupt approval challenge expiry: ${expiresAt}`, "E_RSI_STORE_CORRUPT", 1);
  }
  return Date.parse(nowIso) >= expires;
}

export interface CreateRollbackPointOptions extends StoreOptions {
  baseCommit: string;
  baseVersion: string;
  /** Optional artifact inside the project; its sha256 is recorded. */
  artifactPath?: string;
  note?: string;
}

/**
 * Record where a human can return to if the change misbehaves. Creating a point
 * has no side effects on the working tree, branch or package.
 */
export async function createRollbackPoint(options: CreateRollbackPointOptions): Promise<RollbackPoint> {
  const store = resolveRsiStore(options);
  const createdAt = store.nowIso();
  const baseCommit = validateBaseCommit(options.baseCommit);
  const baseVersion = validateBaseVersion(options.baseVersion);
  const point: RollbackPoint = {
    schemaVersion: RSI_SCHEMA_VERSION,
    id: newRsiId("rb", createdAt),
    createdAt,
    baseVersion,
    baseCommit,
    // Guidance only: the skeleton never runs git or any rollback command.
    rollbackCommand: `git checkout ${baseCommit}`,
  };
  const note = optionalCleanText(options.note, "note", 2_000);
  if (note !== undefined) point.note = note;
  if (options.artifactPath !== undefined) {
    const artifact = isAbsolute(options.artifactPath)
      ? resolve(options.artifactPath)
      : resolve(store.projectRoot, options.artifactPath);
    if (!isPathInside(store.projectRoot, artifact)) {
      throw new SageError(`Rollback artifact must be inside the project: ${options.artifactPath}`, "E_RSI_UNSAFE_PATH", 2);
    }
    let bytes: Buffer;
    try {
      bytes = await readFile(artifact);
    } catch {
      throw new SageError(`Rollback artifact not found: ${artifact}`, "E_RSI_ROLLBACK_ARTIFACT_NOT_FOUND", 1);
    }
    point.artifactSha256 = sha256(bytes);
  }
  await store.saveRollbackPoint(point);
  return point;
}

export interface RequestApprovalOptions extends StoreOptions {
  proposalId: string;
  /** Challenge lifetime; defaults to 24h. The token is returned once, never stored. */
  approvalTtlMs?: number;
}

export interface ApprovalChallenge {
  proposalId: string;
  /** Plaintext one-time token; persist nowhere — show it to the human once. */
  approvalToken: string;
  expiresAt: string;
}

/**
 * Create a one-time approval challenge for a proposal whose evaluation passed.
 * Returns the only copy of the plaintext token; only its hash is stored.
 */
export async function requestApproval(options: RequestApprovalOptions): Promise<ApprovalChallenge> {
  const store = resolveRsiStore(options);
  const proposalId = validateRsiId(options.proposalId, "proposalId");
  const proposal = await store.getProposal(proposalId);
  if (proposal.status === "approved" || proposal.status === "rejected") {
    throw new SageError(`Proposal ${proposalId} was already decided (${proposal.status})`, "E_RSI_ALREADY_DECIDED", 1);
  }
  if (proposal.status !== "awaiting_approval") {
    throw new SageError(
      `Proposal ${proposalId} is ${proposal.status}; only a passed evaluation can request approval`,
      "E_RSI_NOT_AWAITING_APPROVAL",
      1,
    );
  }
  if (proposal.evaluationId === undefined) {
    throw new SageError(`Proposal ${proposalId} has no evaluation record`, "E_RSI_EVALUATION_NOT_FOUND", 1);
  }
  const evaluation = await store.getEvaluation(proposal.evaluationId);
  if (evaluation.outcome !== "passed") {
    throw new SageError(`Evaluation ${evaluation.id} did not pass; approval is blocked`, "E_RSI_NOT_AWAITING_APPROVAL", 1);
  }
  const ttl = options.approvalTtlMs ?? DEFAULT_APPROVAL_TTL_MS;
  if (!Number.isInteger(ttl) || ttl <= 0) {
    throw new SageError("approvalTtlMs must be a positive integer", "E_RSI_BAD_APPROVAL", 2);
  }
  const createdAt = store.nowIso();
  const expiresAt = new Date(Date.parse(createdAt) + ttl).toISOString();
  const approvalToken = randomBytes(16).toString("hex");
  await store.saveProposal({
    ...proposal,
    approvalChallenge: { tokenHash: sha256(approvalToken), createdAt, expiresAt },
    updatedAt: createdAt,
  });
  return { proposalId, approvalToken, expiresAt };
}

export interface ApproveOptions extends StoreOptions {
  proposalId: string;
  approvalToken: string;
  /** Explicit human actor; approvals are never anonymous. */
  decidedBy: string;
  /** Rollback point for the proposal's base commit/version (required). */
  rollbackPointId: string;
  note?: string;
}

/**
 * Apply an explicit human approval. On success the proposal becomes `approved`
 * and the approval record references the passed evaluation and rollback point.
 * Nothing is merged, published or rewritten.
 */
export async function approve(options: ApproveOptions): Promise<Approval> {
  const store = resolveRsiStore(options);
  const proposalId = validateRsiId(options.proposalId, "proposalId");
  const proposal = await store.getProposal(proposalId);
  if (proposal.status === "approved" || proposal.status === "rejected") {
    throw new SageError(`Proposal ${proposalId} was already decided (${proposal.status})`, "E_RSI_ALREADY_DECIDED", 1);
  }
  if (proposal.status !== "awaiting_approval") {
    throw new SageError(
      `Proposal ${proposalId} is ${proposal.status}; approval requires a passed evaluation`,
      "E_RSI_NOT_AWAITING_APPROVAL",
      1,
    );
  }
  const decidedBy = cleanText(options.decidedBy, "decidedBy", 200, "E_RSI_BAD_APPROVAL");
  const approvalToken = requireApprovalToken(options.approvalToken);
  const challenge = proposal.approvalChallenge;
  if (challenge === undefined) {
    throw new SageError(
      `No approval challenge for ${proposalId}; call requestApproval() first`,
      "E_RSI_APPROVAL_NOT_REQUESTED",
      1,
    );
  }
  if (approvalExpired(challenge.expiresAt, store.nowIso())) {
    throw new SageError(`Approval challenge for ${proposalId} has expired`, "E_RSI_APPROVAL_EXPIRED", 1);
  }
  if (!tokenHashMatches(approvalToken, challenge.tokenHash)) {
    throw new SageError(`Approval token for ${proposalId} is invalid`, "E_RSI_APPROVAL_TOKEN_INVALID", 1);
  }
  if (proposal.evaluationId === undefined) {
    throw new SageError(`Proposal ${proposalId} has no evaluation record`, "E_RSI_EVALUATION_NOT_FOUND", 1);
  }
  const evaluation = await store.getEvaluation(proposal.evaluationId);
  if (evaluation.outcome !== "passed") {
    throw new SageError(`Evaluation ${evaluation.id} did not pass; approval is blocked`, "E_RSI_NOT_AWAITING_APPROVAL", 1);
  }
  const rollbackPointId = validateRsiId(options.rollbackPointId, "rollbackPointId", "E_RSI_BAD_APPROVAL");
  let rollbackPoint: RollbackPoint;
  try {
    rollbackPoint = await store.getRollbackPoint(rollbackPointId);
  } catch (error) {
    if (error instanceof SageError && error.code === "E_RSI_NOT_FOUND") {
      throw new SageError(`Rollback point not found: ${rollbackPointId}`, "E_RSI_ROLLBACK_POINT_NOT_FOUND", 1);
    }
    throw error;
  }
  if (rollbackPoint.baseCommit !== proposal.baseCommit || rollbackPoint.baseVersion !== proposal.baseVersion) {
    throw new SageError(
      `Rollback point ${rollbackPointId} is for ${rollbackPoint.baseVersion}@${rollbackPoint.baseCommit}, not ${proposal.baseVersion}@${proposal.baseCommit}`,
      "E_RSI_ROLLBACK_POINT_MISMATCH",
      1,
    );
  }
  const note = optionalCleanText(options.note, "note", 2_000, "E_RSI_BAD_APPROVAL");
  const decidedAt = store.nowIso();
  const approval: Approval = {
    schemaVersion: RSI_SCHEMA_VERSION,
    id: newRsiId("appr", decidedAt),
    proposalId,
    decision: "approved",
    decidedBy,
    decidedAt,
    ...(note === undefined ? {} : { note }),
    evaluationId: evaluation.id,
    rollbackPointId,
    rollbackCommand: rollbackPoint.rollbackCommand,
  };
  await store.saveApproval(approval);
  const updated: Proposal = {
    ...proposal,
    status: "approved",
    approvalId: approval.id,
    rollbackPointId,
    decidedAt,
    updatedAt: decidedAt,
  };
  delete updated.approvalChallenge;
  await store.saveProposal(updated);
  return approval;
}

export interface RejectProposalOptions extends StoreOptions {
  proposalId: string;
  decidedBy: string;
  reason: string;
}

/** Human rejection (still an explicit decision; no rollback point is needed). */
export async function rejectProposal(options: RejectProposalOptions): Promise<Approval> {
  const store = resolveRsiStore(options);
  const proposalId = validateRsiId(options.proposalId, "proposalId");
  const proposal = await store.getProposal(proposalId);
  if (proposal.status === "approved" || proposal.status === "rejected") {
    throw new SageError(`Proposal ${proposalId} was already decided (${proposal.status})`, "E_RSI_ALREADY_DECIDED", 1);
  }
  if (proposal.status === "evaluating") {
    throw new SageError(`Proposal ${proposalId} is being evaluated`, "E_RSI_BAD_TRANSITION", 1);
  }
  const decidedBy = cleanText(options.decidedBy, "decidedBy", 200, "E_RSI_BAD_APPROVAL");
  const reason = cleanText(options.reason, "reason", 2_000, "E_RSI_BAD_APPROVAL");
  const decidedAt = store.nowIso();
  const approval: Approval = {
    schemaVersion: RSI_SCHEMA_VERSION,
    id: newRsiId("appr", decidedAt),
    proposalId,
    decision: "rejected",
    decidedBy,
    decidedAt,
    note: reason,
    ...(proposal.evaluationId === undefined ? {} : { evaluationId: proposal.evaluationId }),
  };
  await store.saveApproval(approval);
  const updated: Proposal = {
    ...proposal,
    status: "rejected",
    approvalId: approval.id,
    decidedAt,
    updatedAt: decidedAt,
  };
  delete updated.approvalChallenge;
  await store.saveProposal(updated);
  return approval;
}
