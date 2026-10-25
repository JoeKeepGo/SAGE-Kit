/**
 * File-mode RSI store: proposals, evaluations, approvals and rollback points.
 *
 * One authoritative writer (this project's `.sage-kit/rsi/` tree, D-005). Writes
 * are atomic (`writeJsonAtomic`) and each record is one JSON file, so a partial
 * write can never produce a silently half-valid proposal. Reads validate the
 * record shape and fail loudly with `E_RSI_STORE_CORRUPT` instead of returning
 * partial data.
 *
 * M2 boundary: `src/control/**` (SQLite tasks/runs/events/leases) has no
 * proposal/evaluation/approval entities yet. This store is therefore the single
 * authority for M3 state; see docs/m3-rsi.md for the documented integration gap.
 */
import { readFile, readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { SageError } from "../core/errors.js";
import { ensureDir, exists, writeJsonAtomic } from "../core/fs-utils.js";
import {
  approvalFile,
  ensureRsiPaths,
  evaluationFile,
  newRsiId,
  proposalFile,
  rollbackPointFile,
  rsiPaths,
  type RsiPaths,
} from "./paths.js";
import {
  RSI_SCHEMA_VERSION,
  isProposalStatus,
  type Approval,
  type CandidateFile,
  type CreateProposalInput,
  type Evaluation,
  type EvaluationBaseline,
  type EvaluationComparison,
  type EvaluationRun,
  type EvaluationWorktree,
  type Proposal,
  type ProposalStatus,
  type RollbackPoint,
  type RsiStoreOptions,
} from "./types.js";
import { RSI_ID_PATTERN, validateProposalInput, validateRsiId } from "./validate.js";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function corrupt(file: string, detail: string): never {
  throw new SageError(`Corrupt RSI record ${file}: ${detail}`, "E_RSI_STORE_CORRUPT", 1);
}

function readSchema(record: Record<string, unknown>, file: string): void {
  if (record.schemaVersion !== RSI_SCHEMA_VERSION) {
    corrupt(file, `schemaVersion must be ${RSI_SCHEMA_VERSION}`);
  }
}

function readId(record: Record<string, unknown>, file: string): string {
  const id = record.id;
  if (typeof id !== "string" || !RSI_ID_PATTERN.test(id)) corrupt(file, "id is invalid");
  return id;
}

function readText(record: Record<string, unknown>, key: string, file: string): string {
  const value = record[key];
  if (typeof value !== "string") corrupt(file, `${key} is not text`);
  return value;
}

function readOptionalText(record: Record<string, unknown>, key: string, file: string): string | undefined {
  const value = record[key];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string") corrupt(file, `${key} is not text`);
  return value;
}

function readNumber(record: Record<string, unknown>, key: string, file: string): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) corrupt(file, `${key} is not a number`);
  return value;
}

function readStringList(value: unknown, key: string, file: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    corrupt(file, `${key} is not a string array`);
  }
  return value as string[];
}

function readCandidate(value: unknown, file: string): { path: string; content: string | null }[] {
  if (!Array.isArray(value)) corrupt(file, "candidate.files is not an array");
  return value.map((item, index) => {
    if (!isRecord(item)) corrupt(file, `candidate.files[${index}] is not an object`);
    const path = item.path;
    const content = item.content;
    if (typeof path !== "string") corrupt(file, `candidate.files[${index}].path is not text`);
    if (content !== null && typeof content !== "string") {
      corrupt(file, `candidate.files[${index}].content is not text or null`);
    }
    return { path, content };
  });
}

function decodeProposal(raw: unknown, file: string): Proposal {
  if (!isRecord(raw)) corrupt(file, "record is not an object");
  readSchema(raw, file);
  readId(raw, file);
  const status = raw.status;
  if (!isProposalStatus(status)) corrupt(file, "status is invalid");
  readText(raw, "createdAt", file);
  readText(raw, "updatedAt", file);
  readText(raw, "baseVersion", file);
  readText(raw, "baseCommit", file);
  readText(raw, "hypothesis", file);
  readText(raw, "validationPlan", file);
  readText(raw, "rollbackPlan", file);
  readStringList(raw.scope, "scope", file);
  readStringList(raw.risks, "risks", file);
  readNumber(raw, "attempts", file);
  if (!isRecord(raw.candidate)) corrupt(file, "candidate is not an object");
  readCandidate(raw.candidate.files, file);
  if (!Array.isArray(raw.feedbackRefs)) corrupt(file, "feedbackRefs is not an array");
  for (const ref of raw.feedbackRefs) {
    if (!isRecord(ref) || ref.untrustedData !== true) corrupt(file, "feedbackRefs item is invalid");
  }
  for (const key of ["note", "evaluationId", "approvalId", "rollbackPointId", "decidedAt"] as const) {
    readOptionalText(raw, key, file);
  }
  if (raw.approvalChallenge !== undefined) {
    if (!isRecord(raw.approvalChallenge)) corrupt(file, "approvalChallenge is not an object");
    readText(raw.approvalChallenge, "tokenHash", file);
    readText(raw.approvalChallenge, "createdAt", file);
    readText(raw.approvalChallenge, "expiresAt", file);
  }
  return raw as unknown as Proposal;
}

function decodeEvaluationWorktree(value: unknown, file: string): EvaluationWorktree {
  if (!isRecord(value)) corrupt(file, "worktree is not an object");
  if (value.kind !== "git-worktree") corrupt(file, "worktree.kind is invalid");
  readText(value, "path", file);
  if (typeof value.removed !== "boolean") corrupt(file, "worktree.removed is invalid");
  return value as unknown as EvaluationWorktree;
}

function decodeEvaluationRun(value: unknown, file: string, field: string): EvaluationRun {
  if (!isRecord(value)) corrupt(file, `${field} is not an object`);
  readNumber(value, "index", file);
  if (value.kind !== "baseline" && value.kind !== "candidate") corrupt(file, `${field}.kind is invalid`);
  if (typeof value.applied !== "boolean" || typeof value.ranTests !== "boolean") {
    corrupt(file, `${field}.applied/ranTests are invalid`);
  }
  if (value.outcome !== "passed" && value.outcome !== "failed") corrupt(file, `${field}.outcome is invalid`);
  if (value.exitCode !== null && typeof value.exitCode !== "number") corrupt(file, `${field}.exitCode is invalid`);
  if (value.signal !== null && typeof value.signal !== "string") corrupt(file, `${field}.signal is invalid`);
  if (typeof value.timedOut !== "boolean") corrupt(file, `${field}.timedOut is invalid`);
  readNumber(value, "durationMs", file);
  readOptionalText(value, "reasonCode", file);
  readOptionalText(value, "reasonMessage", file);
  if (!isRecord(value.protectedAssets)) corrupt(file, `${field}.protectedAssets is not an object`);
  if (typeof value.protectedAssets.ok !== "boolean") corrupt(file, `${field}.protectedAssets.ok is invalid`);
  readStringList(value.protectedAssets.paths, `${field}.protectedAssets.paths`, file);
  readStringList(value.protectedAssets.changed, `${field}.protectedAssets.changed`, file);
  if (!isRecord(value.log)) corrupt(file, `${field}.log is not an object`);
  readText(value.log, "stdout", file);
  readText(value.log, "stderr", file);
  if (typeof value.log.truncated !== "boolean") corrupt(file, `${field}.log.truncated is invalid`);
  decodeEvaluationWorktree(value.worktree, file);
  return value as unknown as EvaluationRun;
}

function decodeEvaluationBaseline(value: unknown, file: string): EvaluationBaseline {
  if (!isRecord(value)) corrupt(file, "baseline is not an object");
  if (!Array.isArray(value.runs)) corrupt(file, "baseline.runs is not an array");
  const runs = value.runs.map((run, index) => decodeEvaluationRun(run, file, `baseline.runs[${index}]`));
  readNumber(value, "passedRuns", file);
  readNumber(value, "failedRuns", file);
  if (value.outcome !== "passed" && value.outcome !== "failed" && value.outcome !== "not_run") {
    corrupt(file, "baseline.outcome is invalid");
  }
  return { ...(value as unknown as EvaluationBaseline), runs };
}

function decodeEvaluationComparison(value: unknown, file: string): EvaluationComparison {
  if (!isRecord(value)) corrupt(file, "comparison is not an object");
  readNumber(value, "candidateRuns", file);
  readNumber(value, "baselineRuns", file);
  readNumber(value, "candidatePassedRuns", file);
  readNumber(value, "baselinePassedRuns", file);
  if (typeof value.noWeakerThanBaseline !== "boolean") corrupt(file, "comparison.noWeakerThanBaseline is invalid");
  return value as unknown as EvaluationComparison;
}

function decodeEvaluation(raw: unknown, file: string): Evaluation {
  if (!isRecord(raw)) corrupt(file, "record is not an object");
  readSchema(raw, file);
  readId(raw, file);
  readText(raw, "proposalId", file);
  const outcome = raw.outcome;
  if (outcome !== "passed" && outcome !== "failed") corrupt(file, "outcome is invalid");
  readNumber(raw, "attempt", file);
  readText(raw, "startedAt", file);
  readText(raw, "finishedAt", file);
  readText(raw, "baseCommit", file);
  readNumber(raw, "repeats", file);
  readStringList(raw.command, "command", file);
  if (raw.exitCode !== null && typeof raw.exitCode !== "number") corrupt(file, "exitCode is invalid");
  if (raw.signal !== null && typeof raw.signal !== "string") corrupt(file, "signal is invalid");
  if (typeof raw.timedOut !== "boolean" || typeof raw.ranTests !== "boolean") corrupt(file, "flags are invalid");
  readNumber(raw, "durationMs", file);
  if (!isRecord(raw.diff)) corrupt(file, "diff is not an object");
  readNumber(raw.diff, "files", file);
  readNumber(raw.diff, "changedLines", file);
  if (!isRecord(raw.diff.limits)) corrupt(file, "diff.limits is not an object");
  readNumber(raw.diff.limits, "maxFiles", file);
  readNumber(raw.diff.limits, "maxChangedLines", file);
  if (!isRecord(raw.protectedAssets)) corrupt(file, "protectedAssets is not an object");
  if (typeof raw.protectedAssets.ok !== "boolean") corrupt(file, "protectedAssets.ok is invalid");
  readStringList(raw.protectedAssets.paths, "protectedAssets.paths", file);
  readStringList(raw.protectedAssets.changed, "protectedAssets.changed", file);
  if (!isRecord(raw.log)) corrupt(file, "log is not an object");
  readText(raw.log, "stdout", file);
  readText(raw.log, "stderr", file);
  if (typeof raw.log.truncated !== "boolean") corrupt(file, "log.truncated is invalid");
  if (!Array.isArray(raw.runs)) corrupt(file, "runs is not an array");
  const runs = raw.runs.map((run, index) => decodeEvaluationRun(run, file, `runs[${index}]`));
  decodeEvaluationBaseline(raw.baseline, file);
  decodeEvaluationComparison(raw.comparison, file);
  readOptionalText(raw, "reasonCode", file);
  readOptionalText(raw, "reasonMessage", file);
  return { ...(raw as unknown as Evaluation), runs };
}

function decodeApproval(raw: unknown, file: string): Approval {
  if (!isRecord(raw)) corrupt(file, "record is not an object");
  readSchema(raw, file);
  readId(raw, file);
  readText(raw, "proposalId", file);
  const decision = raw.decision;
  if (decision !== "approved" && decision !== "rejected") corrupt(file, "decision is invalid");
  readText(raw, "decidedBy", file);
  readText(raw, "decidedAt", file);
  for (const key of ["note", "evaluationId", "rollbackPointId", "rollbackCommand"] as const) {
    readOptionalText(raw, key, file);
  }
  return raw as unknown as Approval;
}

function decodeRollbackPoint(raw: unknown, file: string): RollbackPoint {
  if (!isRecord(raw)) corrupt(file, "record is not an object");
  readSchema(raw, file);
  readId(raw, file);
  readText(raw, "createdAt", file);
  readText(raw, "baseVersion", file);
  readText(raw, "baseCommit", file);
  readText(raw, "rollbackCommand", file);
  readOptionalText(raw, "artifactSha256", file);
  readOptionalText(raw, "note", file);
  return raw as unknown as RollbackPoint;
}

async function readRecord<T>(file: string, decode: (raw: unknown, file: string) => T): Promise<T> {
  let content: string;
  try {
    content = await readFile(file, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      throw new SageError(`RSI record not found: ${file}`, "E_RSI_NOT_FOUND", 1);
    }
    throw error;
  }
  let raw: unknown;
  try {
    raw = JSON.parse(content) as unknown;
  } catch {
    corrupt(file, "invalid JSON");
  }
  return decode(raw, file);
}

function assertRecordId<T extends { id: string }>(record: T, expected: string, file: string): T {
  if (record.id !== expected) {
    corrupt(file, `record id ${record.id} does not match ${expected}`);
  }
  return record;
}

async function listRecords<T extends { id: string }>(
  dir: string,
  decode: (raw: unknown, file: string) => T,
): Promise<T[]> {
  let names: string[];
  try {
    names = await readdir(dir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
  const records: T[] = [];
  for (const name of names.filter((item) => item.endsWith(".json")).sort()) {
    const file = join(dir, name);
    records.push(assertRecordId(await readRecord(file, decode), name.slice(0, -5), file));
  }
  return records;
}

export interface ListProposalsOptions {
  status?: ProposalStatus;
}

export interface ListEvaluationsOptions {
  proposalId?: string;
}

export interface ListApprovalsOptions {
  proposalId?: string;
}

/**
 * File-mode RSI store. Methods are async because file writes use the same
 * atomic writer as the rest of file mode; a store instance holds no OS lock —
 * the evaluation lock is a separate short-lived file (see `lock.ts`).
 */
export class RsiStore {
  readonly projectRoot: string;
  readonly paths: RsiPaths;
  private readonly clock: () => Date;

  constructor(projectRoot: string, options: RsiStoreOptions = {}) {
    this.projectRoot = resolve(projectRoot);
    this.paths = rsiPaths(this.projectRoot);
    this.clock = options.clock ?? ((): Date => new Date());
  }

  nowIso(): string {
    return this.clock().toISOString();
  }

  // ---- proposals ----------------------------------------------------------

  async createProposal(input: CreateProposalInput): Promise<Proposal> {
    const normalized = validateProposalInput(input);
    const createdAt = this.nowIso();
    const id =
      input.id === undefined
        ? newRsiId("prop", createdAt)
        : validateRsiId(input.id, "id", "E_RSI_BAD_PROPOSAL");
    if (await exists(proposalFile(this.paths, id))) {
      throw new SageError(`Proposal already exists: ${id}`, "E_RSI_PROPOSAL_EXISTS", 1);
    }
    const proposal: Proposal = {
      schemaVersion: RSI_SCHEMA_VERSION,
      id,
      createdAt,
      updatedAt: createdAt,
      feedbackRefs: normalized.feedbackRefs,
      baseVersion: normalized.baseVersion,
      baseCommit: normalized.baseCommit,
      hypothesis: normalized.hypothesis,
      scope: normalized.scope,
      risks: normalized.risks,
      validationPlan: normalized.validationPlan,
      rollbackPlan: normalized.rollbackPlan,
      candidate: normalized.candidate,
      ...(normalized.note === undefined ? {} : { note: normalized.note }),
      status: "proposed",
      attempts: 0,
    };
    await this.saveProposal(proposal);
    return proposal;
  }

  /** Persist a proposal record (used by the evaluator/approval state machine). */
  async saveProposal(proposal: Proposal): Promise<void> {
    const id = validateRsiId(proposal.id);
    await ensureDir(this.paths.proposalsDir);
    await writeJsonAtomic(proposalFile(this.paths, id), proposal);
  }

  async getProposal(id: string): Promise<Proposal> {
    const proposalId = validateRsiId(id);
    const file = proposalFile(this.paths, proposalId);
    return assertRecordId(await readRecord(file, decodeProposal), proposalId, file);
  }

  /** Oldest proposal first; `runOnce` relies on this order. */
  async listProposals(options: ListProposalsOptions = {}): Promise<Proposal[]> {
    const proposals = await listRecords(this.paths.proposalsDir, decodeProposal);
    const filtered =
      options.status === undefined ? proposals : proposals.filter((proposal) => proposal.status === options.status);
    return filtered.sort(
      (a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id),
    );
  }

  // ---- evaluations --------------------------------------------------------

  async saveEvaluation(evaluation: Evaluation): Promise<void> {
    const id = validateRsiId(evaluation.id);
    await ensureDir(this.paths.evaluationsDir);
    await writeJsonAtomic(evaluationFile(this.paths, id), evaluation);
  }

  async getEvaluation(id: string): Promise<Evaluation> {
    const evaluationId = validateRsiId(id);
    const file = evaluationFile(this.paths, evaluationId);
    return assertRecordId(await readRecord(file, decodeEvaluation), evaluationId, file);
  }

  async listEvaluations(options: ListEvaluationsOptions = {}): Promise<Evaluation[]> {
    const evaluations = await listRecords(this.paths.evaluationsDir, decodeEvaluation);
    const filtered =
      options.proposalId === undefined
        ? evaluations
        : evaluations.filter((evaluation) => evaluation.proposalId === options.proposalId);
    return filtered.sort(
      (a, b) => a.startedAt.localeCompare(b.startedAt) || a.id.localeCompare(b.id),
    );
  }

  // ---- approvals ----------------------------------------------------------

  async saveApproval(approval: Approval): Promise<void> {
    const id = validateRsiId(approval.id);
    await ensureDir(this.paths.approvalsDir);
    await writeJsonAtomic(approvalFile(this.paths, id), approval);
  }

  async getApproval(id: string): Promise<Approval> {
    const approvalId = validateRsiId(id);
    const file = approvalFile(this.paths, approvalId);
    return assertRecordId(await readRecord(file, decodeApproval), approvalId, file);
  }

  async listApprovals(options: ListApprovalsOptions = {}): Promise<Approval[]> {
    const approvals = await listRecords(this.paths.approvalsDir, decodeApproval);
    const filtered =
      options.proposalId === undefined
        ? approvals
        : approvals.filter((approval) => approval.proposalId === options.proposalId);
    return filtered.sort(
      (a, b) => a.decidedAt.localeCompare(b.decidedAt) || a.id.localeCompare(b.id),
    );
  }

  // ---- rollback points ----------------------------------------------------

  async saveRollbackPoint(point: RollbackPoint): Promise<void> {
    const id = validateRsiId(point.id);
    await ensureDir(this.paths.rollbackPointsDir);
    await writeJsonAtomic(rollbackPointFile(this.paths, id), point);
  }

  async getRollbackPoint(id: string): Promise<RollbackPoint> {
    const pointId = validateRsiId(id);
    const file = rollbackPointFile(this.paths, pointId);
    return assertRecordId(await readRecord(file, decodeRollbackPoint), pointId, file);
  }

  async listRollbackPoints(): Promise<RollbackPoint[]> {
    const points = await listRecords(this.paths.rollbackPointsDir, decodeRollbackPoint);
    return points.sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id));
  }
}

/** Open the file-mode RSI store for a project root. */
export function openRsi(projectRoot: string, options: RsiStoreOptions = {}): RsiStore {
  return new RsiStore(projectRoot, options);
}

/** Resolve `{projectRoot}` / `{store}` options into a store instance. */
export function resolveRsiStore(options: { projectRoot?: string; store?: RsiStore }): RsiStore {
  if (options.store !== undefined) return options.store;
  if (options.projectRoot === undefined) {
    throw new SageError("projectRoot or store is required", "E_RSI_BAD_INPUT", 2);
  }
  return openRsi(options.projectRoot);
}

/** Exported for callers that want the directory contract without a store. */
export { ensureRsiPaths };
export type { CandidateFile };
