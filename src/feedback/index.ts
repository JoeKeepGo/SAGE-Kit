/**
 * Public M1 feedback module surface.
 *
 * `runFeedbackCommand` is the CLI integration point owned by the Lead; the rest
 * is exported for tests, docs and future proposal tooling (M2).
 */
export * from "./types.js";
export * from "./normalize.js";
export * from "./store.js";
export * from "./sync.js";
export { runFeedbackCommand, feedbackUsage } from "./command.js";
export { createFeedbackAdapter } from "./adapters/index.js";
