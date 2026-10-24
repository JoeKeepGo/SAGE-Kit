/**
 * Public M3 RSI surface (schema v2: git-worktree evaluation, baseline
 * comparison, bounded repeats).
 *
 * The module owns proposal/evaluation/approval/rollback-point state in
 * `.sage-kit/rsi/` and never merges, publishes, rewrites `SKILL.md`, starts a
 * scheduler, calls a model or opens a network connection by itself.
 *
 * Evaluation does require the *git* command (worktree checkout); it never
 * fetches, so the proposal base commit must already exist locally.
 *
 * CLI wiring is owned by the Lead (`src/cli.ts`); this slice only exports the
 * library API plus the state paths needed for integration and tests.
 */
export {
  DEFAULT_APPROVAL_TTL_MS,
  DEFAULT_PROTECTED_PATHS,
  DEFAULT_REPEATS,
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
  EvaluationBaseline,
  EvaluationComparison,
  EvaluationLog,
  EvaluationOutcome,
  EvaluationRun,
  EvaluationRunKind,
  EvaluationWorktree,
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
  DEFAULT_GIT_TIMEOUT_MS,
  createEvaluationWorktree,
  resolveBaseCommit,
  resolveGitRepository,
  runGitCommand,
} from "./worktree.js";
export type {
  CreateWorktreeOptions,
  GitCommandResult,
  GitWorktreeHandle,
} from "./worktree.js";

export { exportEvaluationSummary } from "./export.js";
export type {
  EvaluationSummary,
  ExportEvaluationOptions,
  ExportEvaluationResult,
} from "./export.js";

export { recordEvaluationInControl } from "./control-record.js";
export type {
  EvaluationControlRecord,
  RecordEvaluationInControlOptions,
} from "./control-record.js";
