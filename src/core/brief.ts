import { truncateUtf8 } from "./fs-utils.js";
import { SageError } from "./errors.js";
import { findActiveTask, listTasks, readTask } from "./tasks.js";
import type { StatePaths } from "./paths.js";

export interface BriefResult {
  text: string;
  taskId?: string;
  truncated: boolean;
}

export async function buildBrief(paths: StatePaths, taskId?: string, maxBytes = 2048): Promise<BriefResult> {
  let task;
  if (taskId) {
    task = await readTask(paths, taskId);
  } else {
    task = findActiveTask(await listTasks(paths));
  }

  if (!task) {
    const text =
      "# SAGE-Kit brief\n\nNo task exists yet.\nCreate one with `sage-kit task create --title \"...\"`.\nDo not claim completion without evidence.";
    const limited = truncateUtf8(text, Math.max(128, Math.min(maxBytes, 8192)));
    return { text: limited.text, truncated: limited.truncated };
  }

  const lines = [
    "# SAGE-Kit brief",
    "",
    `Task: ${task.id}`,
    `Title: ${task.title}`,
    `Status: ${task.status}`,
    ...(task.branch ? [`Branch: ${task.branch}`] : []),
    ...(task.worktree ? [`Worktree: ${task.worktree}`] : []),
    "",
    "Acceptance:",
    ...(task.acceptance.length ? task.acceptance.slice(0, 5).map((item) => `- ${item}`) : ["- (none recorded)"]),
    ...(task.evidence.length
      ? ["", "Latest evidence:", `- ${task.evidence[task.evidence.length - 1]?.note ?? ""}`]
      : ["", "Evidence: none yet"]),
    "",
    "Rules:",
    "- Read before editing; keep changes inside the task scope.",
    "- Run the task's checks and record exact evidence.",
    "- Do not claim done without evidence; stop if blocked.",
  ];
  const limited = truncateUtf8(lines.join("\n"), Math.max(256, Math.min(maxBytes, 8192)));
  return { text: limited.text, taskId: task.id, truncated: limited.truncated };
}

export function assertBriefSize(text: string, maxBytes = 2048): void {
  if (Buffer.byteLength(text, "utf8") > maxBytes) {
    throw new SageError(`Brief exceeds ${maxBytes} bytes`, "E_BRIEF_TOO_LARGE", 1);
  }
}
