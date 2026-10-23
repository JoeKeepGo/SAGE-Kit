/**
 * Public M3 RSI skeleton surface.
 *
 * The module owns proposal/evaluation/approval/rollback-point state in
 * `.sage-kit/rsi/` and never merges, publishes, rewrites `SKILL.md`, starts a
 * scheduler, calls a model or opens a network connection by itself.
 *
 * CLI wiring is owned by the Lead (`src/cli.ts`); this slice only exports the
 * library API plus the state paths needed for integration and tests.
 */
export {
  DEFAULT_APPROVAL_TTL_MS,
  DEFAULT_PROTECTED_PATHS,
  DEFAULT_RSI_LIMITS,
  MAX_FEEDBACK_REFS,
  RSI_PROPOSAL_STATUSES,
  RSI_SCHEMA_VERSION,
  isProposalStatus,
} from "./types.js";
export type {
  Approval,
  ApprovalDecision,
  Candidate,
  CandidateFile,
  CreateProposalInput,
  Evaluation,
  EvaluationLog,
  EvaluationOutcome,
  FeedbackRefInput,
  Proposal,
  ProposalDiffStats,
  ProposalFeedbackRef,
  ProposalStatus,
  ProtectedAssetReport,
  RollbackPoint,
  RsiLimits,
  RsiStoreOptions,
  RunOnceResult,
} from "./types.js";

export {
  approvalFile,
  ensureRsiPaths,
  evaluationFile,
  newRsiId,
  proposalFile,
  rollbackPointFile,
  rsiPaths,
} from "./paths.js";
export type { RsiIdPrefix, RsiPaths } from "./paths.js";

export {
  RsiStore,
  openRsi,
  resolveRsiStore,
} from "./store.js";
export type {
  ListApprovalsOptions,
  ListEvaluationsOptions,
  ListProposalsOptions,
} from "./store.js";

export { acquireEvaluationLock } from "./lock.js";
export type { EvaluationLock } from "./lock.js";

export { evaluateCandidate } from "./evaluate.js";
export type { EvaluateCandidateOptions } from "./evaluate.js";

export { runOnce } from "./run.js";
export type { RunOnceOptions } from "./run.js";

export {
  approve,
  createRollbackPoint,
  rejectProposal,
  requestApproval,
} from "./approve.js";
export type {
  ApprovalChallenge,
  ApproveOptions,
  CreateRollbackPointOptions,
  RejectProposalOptions,
  RequestApprovalOptions,
} from "./approve.js";

export { runFixedCommand } from "./process.js";
export type { FixedCommandResult } from "./process.js";

export {
  DEFAULT_COPY_EXCLUDE,
  createEvaluationWorkspace,
} from "./workspace.js";
export type { CreateWorkspaceOptions, TempProjectCopy } from "./workspace.js";
