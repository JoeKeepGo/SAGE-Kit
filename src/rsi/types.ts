/**
 * M3 RSI types (schema v2: real git worktree evaluation, baseline comparison,
 * repeated runs).
 *
 * DESIGN: docs/feedback-and-rsi.md §5–§9; docs/decisions.md D-011 (RSI stops at
 * L2, human approval only), D-012 (Builder/Evaluator separation, protected
 * evaluation assets) and D-005 (single authoritative writer).
 *
 * This module is still a *skeleton*, not the autonomous loop: proposal,
 * evaluation, approval and rollback-point records are file-mode state under
 * `.sage-kit/rsi/`. Nothing here merges, publishes, rewrites `SKILL.md`, calls a
 * model or opens a network connection by itself.
 */

export const RSI_SCHEMA_VERSION = 2;

export const RSI_PROPOSAL_STATUSES = [
  "proposed",
  "evaluating",
  "failed",
  "awaiting_approval",
  "approved",
  "rejected",
] as const;

export type ProposalStatus = (typeof RSI_PROPOSAL_STATUSES)[number];

export function isProposalStatus(value: unknown): value is ProposalStatus {
  return typeof value === "string" && (RSI_PROPOSAL_STATUSES as readonly string[]).includes(value);
}

export type EvaluationOutcome = "passed" | "failed";
export type EvaluationRunKind = "baseline" | "candidate";
export type ApprovalDecision = "approved" | "rejected";

/**
 * Budgets and limits for one evaluation. Defaults follow
 * docs/feedback-and-rsi.md §5 (diff size), §6 (baseline evidence) and §9 (one
 * candidate at a time, bounded repeats).
 */
export interface RsiLimits {
  /** Maximum number of files a candidate may change. Default 20. */
  maxCandidateFiles: number;
  /** Maximum changed (added + removed) lines across the candidate. Default 500. */
  maxChangedLines: number;
  /** Maximum bytes kept from each of stdout/stderr in one run record. */
  maxLogBytes: number;
  /** Wall-clock budget for one fixed evaluation command (milliseconds). */
  evaluationTimeoutMs: number;
  /** Maximum accepted `repeats` value (evaluation repeats are bounded). */
  maxRepeats: number;
}

export const DEFAULT_REPEATS = 1;

export const DEFAULT_RSI_LIMITS: RsiLimits = {
  maxCandidateFiles: 20,
  maxChangedLines: 500,
  maxLogBytes: 16_384,
  evaluationTimeoutMs: 120_000,
  maxRepeats: 5,
};

/**
 * Evaluation assets a candidate may never modify (D-012 §8). The evaluator
 * re-checks the same set after every candidate run, so a test that rewrites a
 * protected asset is a failed evaluation as well.
 */
export const DEFAULT_PROTECTED_PATHS: readonly string[] = [
  "tests",
  "test",
  "eval",
  "holdout",
  ".github",
  "package.json",
  "package-lock.json",
];

/** Default lifetime of a one-time human approval token (24h). */
export const DEFAULT_APPROVAL_TTL_MS = 24 * 60 * 60 * 1_000;

/** Maximum number of feedback references kept on one proposal. */
export const MAX_FEEDBACK_REFS = 20;

/** External feedback is untrusted data: stored by reference, never executed. */
export interface FeedbackRefInput {
  id?: string;
  url?: string;
  title?: string;
}

export interface ProposalFeedbackRef extends FeedbackRefInput {
  untrustedData: true;
}

/**
 * One candidate file replacement. `content: null` deletes the file.
 *
 * Paths are project-relative POSIX paths. Absolute paths, `..` escapes and the
 * reserved `.git`/`.sage-kit` trees are rejected before evaluation. Candidates
 * are only ever written into an isolated git worktree, never the source tree.
 */
export interface CandidateFile {
  path: string;
  content: string | null;
}

export interface Candidate {
  /** Informational only; the evaluator never asks the builder for more data. */
  builder?: string;
  summary?: string;
  files: CandidateFile[];
}

export interface CreateProposalInput {
  /** Optional caller-supplied id; generated when omitted. */
  id?: string;
  feedbackRefs?: FeedbackRefInput[];
  baseVersion: string;
  /** Base git commit (7–64 lowercase hex characters) used for rollback. */
  baseCommit: string;
  /** What changes and why. */
  hypothesis: string;
  /** Files/modules/interfaces in scope. */
  scope: string[];
  /** Regression, compatibility, security and licensing risks. */
  risks: string[];
  /** Which suites/metrics/thresholds will be run. */
  validationPlan: string;
  /** How a failing release is reverted. */
  rollbackPlan: string;
  candidate: Candidate;
  note?: string;
}

export interface Proposal {
  schemaVersion: typeof RSI_SCHEMA_VERSION;
  id: string;
  createdAt: string;
  updatedAt: string;
  /** Untrusted external references (ids/URLs only; never instructions). */
  feedbackRefs: ProposalFeedbackRef[];
  baseVersion: string;
  baseCommit: string;
  hypothesis: string;
  scope: string[];
  risks: string[];
  validationPlan: string;
  rollbackPlan: string;
  candidate: Candidate;
  note?: string;
  status: ProposalStatus;
  /** Number of evaluation attempts (skeleton: 0 or 1). */
  attempts: number;
  evaluationId?: string;
  approvalId?: string;
  rollbackPointId?: string;
  /** One-time approval challenge (token hash only; token is never persisted). */
  approvalChallenge?: {
    tokenHash: string;
    createdAt: string;
    expiresAt: string;
  };
  decidedAt?: string;
}

export interface ProposalDiffStats {
  files: number;
  changedLines: number;
  limits: {
    maxFiles: number;
    maxChangedLines: number;
  };
}

export interface ProtectedAssetReport {
  paths: string[];
  ok: boolean;
  changed: string[];
}

export interface EvaluationLog {
  stdout: string;
  stderr: string;
  truncated: boolean;
}

/** One isolated git worktree used by a baseline or candidate run. */
export interface EvaluationWorktree {
  kind: "git-worktree";
  /** Worktree root (a detached checkout of the proposal base commit). */
  path: string;
  /** True when the worktree and its temporary parent were removed. */
  removed: boolean;
}

/**
 * One measured run of the fixed evaluation command. Every baseline/candidate
 * run has its own record and its own throwaway worktree.
 */
export interface EvaluationRun {
  /** 1-based repeat index. */
  index: number;
  kind: EvaluationRunKind;
  /** False only when the candidate could not be applied inside the worktree. */
  applied: boolean;
  ranTests: boolean;
  outcome: EvaluationOutcome;
  reasonCode?: string;
  reasonMessage?: string;
  exitCode: number | null;
  signal: string | null;
  timedOut: boolean;
  durationMs: number;
  protectedAssets: ProtectedAssetReport;
  log: EvaluationLog;
  worktree: EvaluationWorktree;
}

/** Baseline evidence: the same fixed command on the unmodified base commit. */
export interface EvaluationBaseline {
  runs: EvaluationRun[];
  passedRuns: number;
  failedRuns: number;
  /** `not_run` when the candidate was rejected before any command ran. */
  outcome: EvaluationOutcome | "not_run";
}

/** Candidate-vs-baseline comparison used by the pass rule. */
export interface EvaluationComparison {
  candidateRuns: number;
  baselineRuns: number;
  candidatePassedRuns: number;
  baselinePassedRuns: number;
  /** True when the candidate passed at least as many runs as the baseline. */
  noWeakerThanBaseline: boolean;
}

export interface Evaluation {
  schemaVersion: typeof RSI_SCHEMA_VERSION;
  id: string;
  proposalId: string;
  attempt: number;
  startedAt: string;
  finishedAt: string;
  /** Fully resolved git commit the worktrees were checked out from. */
  baseCommit: string;
  /** Number of candidate/baseline runs requested (1..limits.maxRepeats). */
  repeats: number;
  /** Exact fixed command the evaluator ran (never supplied by the proposal). */
  command: string[];
  outcome: EvaluationOutcome;
  /** Machine-readable failure reason code (see docs/m3-rsi.md §6). */
  reasonCode?: string;
  reasonMessage?: string;
  /** False when the candidate was rejected before the fixed suite started. */
  ranTests: boolean;
  /** First candidate run's exit code (aggregate convenience field). */
  exitCode: number | null;
  signal: string | null;
  /** True when any candidate run timed out. */
  timedOut: boolean;
  /** Sum of candidate run durations. */
  durationMs: number;
  diff: ProposalDiffStats;
  protectedAssets: ProtectedAssetReport;
  /** First candidate run's (redacted, truncated) log; all logs are in `runs`. */
  log: EvaluationLog;
  /** Candidate runs, oldest first. */
  runs: EvaluationRun[];
  baseline: EvaluationBaseline;
  comparison: EvaluationComparison;
}

export interface Approval {
  schemaVersion: typeof RSI_SCHEMA_VERSION;
  id: string;
  proposalId: string;
  decision: ApprovalDecision;
  /** Explicit human actor; an approval is never anonymous. */
  decidedBy: string;
  decidedAt: string;
  note?: string;
  evaluationId?: string;
  rollbackPointId?: string;
  /** Human-run rollback guidance. The skeleton never executes it. */
  rollbackCommand?: string;
}

export interface RollbackPoint {
  schemaVersion: typeof RSI_SCHEMA_VERSION;
  id: string;
  createdAt: string;
  baseVersion: string;
  baseCommit: string;
  /** sha256 of a release artifact when one was supplied. */
  artifactSha256?: string;
  /** Human-run rollback guidance, e.g. `git checkout <baseCommit>`. */
  rollbackCommand: string;
  note?: string;
}

export interface RunOnceResult {
  outcome: "idle" | "passed" | "failed";
  /** Number of candidates evaluated by this call (0 when idle). */
  evaluated: number;
  proposalId?: string;
  evaluationId?: string;
  status?: ProposalStatus;
  reasonCode?: string;
}

export interface RsiStoreOptions {
  /** Deterministic clock used by tests; defaults to the system clock. */
  clock?: () => Date;
}
