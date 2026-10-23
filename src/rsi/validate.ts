/**
 * Input validation for the RSI skeleton.
 *
 * Everything that crosses the module boundary (proposals from the Builder,
 * fixed test commands from the Evaluator wiring, paths from a candidate) is
 * validated here before it can touch the filesystem.
 */
import { SageError } from "../core/errors.js";
import {
  DEFAULT_PROTECTED_PATHS,
  DEFAULT_RSI_LIMITS,
  MAX_FEEDBACK_REFS,
  type Candidate,
  type CandidateFile,
  type CreateProposalInput,
  type FeedbackRefInput,
  type ProposalFeedbackRef,
  type RsiLimits,
} from "./types.js";

export const RSI_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;
const COMMIT_PATTERN = /^[0-9a-f]{7,64}$/;
const VERSION_PATTERN = /^[0-9A-Za-z][0-9A-Za-z.+-]{0,63}$/;
const RESERVED_CANDIDATE_PREFIXES = [".git", ".sage-kit"] as const;

export function validateRsiId(id: unknown, field = "id", code = "E_RSI_BAD_ID"): string {
  if (typeof id !== "string" || !RSI_ID_PATTERN.test(id)) {
    throw new SageError(`${field} must match ${RSI_ID_PATTERN}`, code, 2);
  }
  return id;
}

export function cleanText(value: unknown, field: string, max: number, code = "E_RSI_BAD_PROPOSAL"): string {
  if (typeof value !== "string") throw new SageError(`${field} must be a string`, code, 2);
  const text = value.trim();
  if (!text) throw new SageError(`${field} must not be empty`, code, 2);
  if (text.length > max) throw new SageError(`${field} must be <= ${max} characters`, code, 2);
  return text;
}

export function optionalCleanText(value: unknown, field: string, max: number, code = "E_RSI_BAD_PROPOSAL"): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string") throw new SageError(`${field} must be a string`, code, 2);
  const text = value.trim();
  if (!text) return undefined;
  if (text.length > max) throw new SageError(`${field} must be <= ${max} characters`, code, 2);
  return text;
}

export function cleanStringList(
  value: unknown,
  field: string,
  maxItems: number,
  maxLength: number,
  code = "E_RSI_BAD_PROPOSAL",
): string[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) throw new SageError(`${field} must be an array of strings`, code, 2);
  if (value.length > maxItems) throw new SageError(`${field} must have <= ${maxItems} items`, code, 2);
  return value.map((item, index) => cleanText(item, `${field}[${index}]`, maxLength, code));
}

export function validateBaseCommit(value: unknown): string {
  const text = cleanText(value, "baseCommit", 64).toLowerCase();
  if (!COMMIT_PATTERN.test(text)) {
    throw new SageError("baseCommit must be 7-64 lowercase hex characters (git commit id)", "E_RSI_BAD_PROPOSAL", 2);
  }
  return text;
}

export function validateBaseVersion(value: unknown): string {
  const text = cleanText(value, "baseVersion", 64);
  if (!VERSION_PATTERN.test(text)) {
    throw new SageError("baseVersion must match [0-9A-Za-z][0-9A-Za-z.+-]{0,63}", "E_RSI_BAD_PROPOSAL", 2);
  }
  return text;
}

export function validateFeedbackRefs(value: FeedbackRefInput[] | undefined): ProposalFeedbackRef[] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) throw new SageError("feedbackRefs must be an array", "E_RSI_BAD_PROPOSAL", 2);
  if (value.length > MAX_FEEDBACK_REFS) {
    throw new SageError(`feedbackRefs must have <= ${MAX_FEEDBACK_REFS} items`, "E_RSI_BAD_PROPOSAL", 2);
  }
  return value.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new SageError(`feedbackRefs[${index}] must be an object`, "E_RSI_BAD_PROPOSAL", 2);
    }
    const id = optionalCleanText(item.id, `feedbackRefs[${index}].id`, 200);
    const url = optionalCleanText(item.url, `feedbackRefs[${index}].url`, 2_000);
    const title = optionalCleanText(item.title, `feedbackRefs[${index}].title`, 200);
    if (id === undefined && url === undefined) {
      throw new SageError(`feedbackRefs[${index}] needs an id or url`, "E_RSI_BAD_PROPOSAL", 2);
    }
    if (url !== undefined && !/^https?:\/\//i.test(url)) {
      // External feedback references are data; only http(s) URLs are recorded.
      throw new SageError(`feedbackRefs[${index}].url must be an http(s) URL`, "E_RSI_BAD_PROPOSAL", 2);
    }
    const ref: ProposalFeedbackRef = { untrustedData: true };
    if (id !== undefined) ref.id = id;
    if (url !== undefined) ref.url = url;
    if (title !== undefined) ref.title = title;
    return ref;
  });
}

/** Normalize a project-relative POSIX path without the candidate-specific checks. */
export function normalizeRelativePath(raw: unknown, field = "path"): string {
  if (typeof raw !== "string") throw new SageError(`${field} must be a string`, "E_RSI_BAD_CANDIDATE", 2);
  const replaced = raw.trim().replace(/\\/g, "/");
  if (!replaced) throw new SageError(`${field} must not be empty`, "E_RSI_BAD_CANDIDATE", 2);
  if (replaced.includes("\0")) throw new SageError(`${field} must not contain NUL bytes`, "E_RSI_BAD_CANDIDATE", 2);
  if (replaced.startsWith("/") || /^[A-Za-z]:/.test(replaced)) {
    throw new SageError(`${field} must be project-relative: ${raw}`, "E_RSI_UNSAFE_PATH", 2);
  }
  const parts = replaced.split("/").filter((part) => part.length > 0 && part !== ".");
  if (parts.some((part) => part === "..")) {
    throw new SageError(`${field} must not escape the project: ${raw}`, "E_RSI_UNSAFE_PATH", 2);
  }
  const normalized = parts.join("/");
  if (!normalized) throw new SageError(`${field} must not be empty`, "E_RSI_BAD_CANDIDATE", 2);
  return normalized;
}

export function normalizeCandidatePath(raw: unknown, field = "candidate path"): string {
  const normalized = normalizeRelativePath(raw, field);
  const lower = normalized.toLowerCase();
  for (const reserved of RESERVED_CANDIDATE_PREFIXES) {
    if (lower === reserved || lower.startsWith(`${reserved}/`)) {
      throw new SageError(`Candidate must not modify ${reserved}/ (reserved path)`, "E_RSI_UNSAFE_PATH", 2);
    }
  }
  return normalized;
}

export function normalizeProtectedPaths(value: readonly string[] | undefined): string[] {
  const list = value === undefined ? DEFAULT_PROTECTED_PATHS : value;
  if (!Array.isArray(list)) throw new SageError("protectedPaths must be an array of strings", "E_RSI_BAD_INPUT", 2);
  const normalized = list.map((item) => normalizeRelativePath(item, "protectedPaths[]"));
  return [...new Set(normalized)].sort();
}

export function isProtectedPath(path: string, protectedPaths: readonly string[]): boolean {
  return protectedPaths.some((protectedPath) => path === protectedPath || path.startsWith(`${protectedPath}/`));
}

export function normalizeLimits(overrides: Partial<RsiLimits> | undefined): RsiLimits {
  const merged = { ...DEFAULT_RSI_LIMITS, ...(overrides ?? {}) };
  for (const [key, value] of Object.entries(merged)) {
    if (!Number.isInteger(value) || value <= 0) {
      throw new SageError(`${key} must be a positive integer`, "E_RSI_BAD_LIMIT", 2);
    }
  }
  return merged;
}

/**
 * The evaluator owns the fixed command; a proposal cannot supply or influence
 * it. No shell is used (`spawn(..., { shell: false })`), so arguments are inert.
 */
export function validateTestCommand(command: unknown): string[] {
  if (!Array.isArray(command) || command.length === 0 || command.length > 64) {
    throw new SageError("testCommand must be a non-empty array of strings (<= 64 items)", "E_RSI_BAD_COMMAND", 2);
  }
  return command.map((item, index) => {
    if (typeof item !== "string" || !item) {
      throw new SageError(`testCommand[${index}] must be a non-empty string`, "E_RSI_BAD_COMMAND", 2);
    }
    if (item.includes("\0") || item.length > 2_000) {
      throw new SageError(`testCommand[${index}] is invalid`, "E_RSI_BAD_COMMAND", 2);
    }
    return item;
  });
}

export interface NormalizedProposalInput {
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
}

/** Validate and normalize everything a proposal may carry. */
export function validateProposalInput(input: CreateProposalInput): NormalizedProposalInput {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new SageError("Proposal input must be an object", "E_RSI_BAD_PROPOSAL", 2);
  }
  const hypothesis = cleanText(input.hypothesis, "hypothesis", 4_000);
  const baseVersion = validateBaseVersion(input.baseVersion);
  const baseCommit = validateBaseCommit(input.baseCommit);
  const scope = cleanStringList(input.scope, "scope", 20, 300);
  const risks = cleanStringList(input.risks, "risks", 20, 500);
  const validationPlan = cleanText(input.validationPlan, "validationPlan", 4_000);
  const rollbackPlan = cleanText(input.rollbackPlan, "rollbackPlan", 4_000);
  const feedbackRefs = validateFeedbackRefs(input.feedbackRefs);
  const note = optionalCleanText(input.note, "note", 2_000);

  const candidateInput = input.candidate;
  if (!candidateInput || typeof candidateInput !== "object" || Array.isArray(candidateInput)) {
    throw new SageError("candidate must be an object", "E_RSI_BAD_PROPOSAL", 2);
  }
  if (!Array.isArray(candidateInput.files) || candidateInput.files.length === 0) {
    throw new SageError("candidate.files must be a non-empty array", "E_RSI_BAD_PROPOSAL", 2);
  }
  const builder = optionalCleanText(candidateInput.builder, "candidate.builder", 200);
  const summary = optionalCleanText(candidateInput.summary, "candidate.summary", 2_000);
  const files: CandidateFile[] = [];
  const seen = new Set<string>();
  candidateInput.files.forEach((file, index) => {
    if (!file || typeof file !== "object" || Array.isArray(file)) {
      throw new SageError(`candidate.files[${index}] must be an object`, "E_RSI_BAD_CANDIDATE", 2);
    }
    const path = normalizeCandidatePath(file.path, `candidate.files[${index}].path`);
    if (file.content !== null && typeof file.content !== "string") {
      throw new SageError(
        `candidate.files[${index}].content must be a string or null`,
        "E_RSI_BAD_CANDIDATE",
        2,
      );
    }
    const key = path.toLowerCase();
    if (seen.has(key)) {
      throw new SageError(`candidate.files has a duplicate path: ${path}`, "E_RSI_BAD_CANDIDATE", 2);
    }
    seen.add(key);
    files.push({ path, content: file.content });
  });
  const candidate: Candidate = { files };
  if (builder !== undefined) candidate.builder = builder;
  if (summary !== undefined) candidate.summary = summary;

  const normalized: NormalizedProposalInput = {
    feedbackRefs,
    baseVersion,
    baseCommit,
    hypothesis,
    scope,
    risks,
    validationPlan,
    rollbackPlan,
    candidate,
  };
  if (note !== undefined) normalized.note = note;
  return normalized;
}
