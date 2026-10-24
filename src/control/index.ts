// SAGE-Kit optional control plane — M2 foundation public API.
//
// This module is additive and lazily loadable: it never changes the P0 file
// mode, never dual-writes `.sage-kit/state/`, and adds no runtime dependency
// (`node:sqlite` is a Node.js built-in; Node >= 22.5 exposes it, Node 24 is the
// supported baseline for M2 — see docs/m2-control.md).
//
// Ownership: `src/control/**`, `tests/control.test.mjs`, `docs/m2-control.md`.
// CLI wiring is deliberately not done here (Lead owns `src/cli.ts`).

export { ControlStore, openControl, recoverStale } from "./store.js";
export type { ListRunsOptions, ListTasksOptions, RecoverStaleOptions } from "./store.js";

export {
  acquireLease,
  expireLeases,
  getLease,
  leaseExpiry,
  listLeases,
  releaseLease,
  renewLease,
  resolveNowIso,
  DEFAULT_HEARTBEAT_MS,
  DEFAULT_LEASE_TTL_MS,
} from "./lease.js";
export type { LeaseListOptions, LeaseStore } from "./lease.js";

export { createControlServer } from "./server.js";
export type { ControlServer, ControlServerOptions } from "./server.js";

export {
  CONTROL_SCHEMA_VERSION,
  DEFAULT_BUSY_TIMEOUT_MS,
  MAX_EVENT_PAYLOAD_BYTES,
  MAX_HTTP_BODY_BYTES,
  RUN_STATUSES,
  TASK_TRANSITIONS,
  controlDbPath,
  controlPaths,
  isRunStatus,
} from "./schema.js";
export type {
  AcquireLeaseOptions,
  AppendEventInput,
  ControlDebugInfo,
  ControlEvent,
  ControlEvidence,
  ControlLease,
  ControlPaths,
  ControlRun,
  ControlStoreOptions,
  ControlTask,
  CreateTaskInput,
  ExpireLeasesOptions,
  FinishRunInput,
  ListEventsOptions,
  RecordRunInput,
  RecoveryReport,
  ReleaseLeaseOptions,
  RenewLeaseOptions,
  RunStatus,
  UpdateTaskStatusOptions,
} from "./schema.js";
export type { TaskStatus } from "../core/tasks.js";
