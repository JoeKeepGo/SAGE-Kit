/**
 * Durable evaluation evidence export.
 *
 * The file-mode store is the authoritative evidence location. This module
 * writes a self-contained JSON summary (proposal + evaluation + linked
 * approvals/rollback point) so a human reviewer or an external tool can inspect
 * one record without walking the state directories.
 *
 * It never publishes, merges or rewrites `SKILL.md`; the export is a plain
 * artifact under `.sage-kit/rsi/exports/` unless the caller names another
 * in-project path.
 */
import { dirname, isAbsolute, join, resolve } from "node:path";
import { SageError } from "../core/errors.js";
import { ensureDir, isPathInside, writeJsonAtomic } from "../core/fs-utils.js";
import { rsiPaths } from "./paths.js";
import { resolveRsiStore, type RsiStore } from "./store.js";
import {
  RSI_SCHEMA_VERSION,
  type Approval,
  type Evaluation,
  type Proposal,
  type RollbackPoint,
} from "./types.js";
import { validateRsiId } from "./validate.js";

export interface EvaluationSummary {
  schemaVersion: typeof RSI_SCHEMA_VERSION;
  exportedAt: string;
  projectRoot: string;
  proposal: Proposal;
  evaluation: Evaluation;
  /** Approval/rejection records for this proposal and evaluation. */
  approvals: Approval[];
  rollbackPoint?: RollbackPoint;
}

export interface ExportEvaluationOptions {
  projectRoot?: string;
  store?: RsiStore;
  evaluationId: string;
  /** Write inside the project root; defaults to `.sage-kit/rsi/exports/<id>.json`. */
  outFile?: string;
  /** Set false to return the summary without writing a file. */
  write?: boolean;
}

export interface ExportEvaluationResult {
  summary: EvaluationSummary;
  filePath?: string;
}

/** Build (and by default persist) one JSON evaluation summary. */
export async function exportEvaluationSummary(
  options: ExportEvaluationOptions,
): Promise<ExportEvaluationResult> {
  const store = resolveRsiStore(options);
  const evaluationId = validateRsiId(options.evaluationId, "evaluationId");
  const evaluation = await store.getEvaluation(evaluationId);
  const proposal = await store.getProposal(evaluation.proposalId);
  const approvals = (await store.listApprovals({ proposalId: proposal.id })).filter(
    (approval) => approval.evaluationId === evaluation.id,
  );

  let rollbackPoint: RollbackPoint | undefined;
  if (proposal.rollbackPointId !== undefined) {
    rollbackPoint = await store.getRollbackPoint(proposal.rollbackPointId);
  }

  const summary: EvaluationSummary = {
    schemaVersion: RSI_SCHEMA_VERSION,
    exportedAt: store.nowIso(),
    projectRoot: store.projectRoot,
    proposal,
    evaluation,
    approvals,
    ...(rollbackPoint === undefined ? {} : { rollbackPoint }),
  };
  if (options.write === false) return { summary };

  let filePath: string;
  if (options.outFile === undefined) {
    filePath = join(rsiPaths(store.projectRoot).exportsDir, `${evaluation.id}.json`);
  } else {
    filePath = isAbsolute(options.outFile)
      ? resolve(options.outFile)
      : resolve(store.projectRoot, options.outFile);
    if (!isPathInside(store.projectRoot, filePath)) {
      throw new SageError(
        `Evaluation summary must be written inside the project: ${options.outFile}`,
        "E_RSI_UNSAFE_PATH",
        2,
      );
    }
  }
  await ensureDir(dirname(filePath));
  await writeJsonAtomic(filePath, summary);
  return { summary, filePath };
}
