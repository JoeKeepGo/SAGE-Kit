from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from sagekit.graph_contract import canonical_graph_digest
from sagekit.ready_resolver import (
    ReadyResolutionIssue,
    ReadyResolutionOutcome,
    canonical_ready_input_digest,
    resolve_ready_nodes,
    validate_ready_resolution_input,
)


INPUT_DIGEST_DOMAIN = b"sagekit-ready-resolution-input-v1\0"
MAX_GRAPH_BYTES = 8 * 1024 * 1024


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def node(
    node_id: str,
    *,
    depends_on: list[str] | None = None,
    resources: list[str] | None = None,
    classification: str = "required",
) -> dict[str, object]:
    return {
        "id": node_id,
        "role": "ready-resolution-vector",
        "depends_on": [] if depends_on is None else depends_on,
        "permission": "READ_ONLY_REVIEW",
        "verifier": "focused-ready-resolution-vector",
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": [] if resources is None else resources,
        "classification": classification,
    }


def graph(
    *,
    nodes: list[dict[str, object]] | None = None,
    joins: list[dict[str, object]] | None = None,
    human_gates: list[str] | None = None,
    generation: int = 1,
) -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "ready-resolution-graph",
        "generation": generation,
        "source_authority": {
            "identity": "Stage 4B test authority",
            "reference": "ready-resolution/stage-4b",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [] if human_gates is None else human_gates,
        "nodes": [node("node-a")] if nodes is None else nodes,
        "joins": [] if joins is None else joins,
    }


def state(
    node_id: str,
    status: str = "PENDING",
    *,
    result_digest: str | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "node_id": node_id,
        "status": status,
        "evidence_refs": [] if evidence_refs is None else evidence_refs,
    }
    if result_digest is not None:
        value["result_digest"] = result_digest
    elif status in {
        "SUCCEEDED",
        "NO_ACTION_REQUIRED",
        "FAILED",
        "NEEDS_CORRECTION",
        "DONE_WITH_CONCERNS",
    }:
        value["result_digest"] = f"node-result:{status.lower()}"
    return value


def resolution_input(
    candidate_graph: dict[str, object],
    *,
    node_states: list[dict[str, object]] | None = None,
    resources: list[dict[str, object]] | None = None,
    external: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    graph_nodes = candidate_graph["nodes"]
    assert isinstance(graph_nodes, list)
    default_states = [state(str(item["id"])) for item in graph_nodes]
    return {
        "schema_id": "urn:sagekit:ready-resolution:v1:input",
        "schema_version": 1,
        "graph_digest": canonical_graph_digest(candidate_graph),
        "graph_generation": candidate_graph["generation"],
        "node_states": default_states if node_states is None else node_states,
        "resource_availability": [] if resources is None else resources,
        "external_join_decisions": [] if external is None else external,
    }


def resource(
    resource_id: str,
    availability: str,
    *,
    evidence_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "resource_id": resource_id,
        "availability": availability,
        "reason_code": f"RESOURCE_{availability}",
        "evidence_refs": [] if evidence_refs is None else evidence_refs,
    }


def external(
    join_id: str,
    decision: str,
    *,
    authority_ref: str = "authority/review",
    evidence_refs: list[str] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {"join_id": join_id, "decision": decision}
    if decision != "PENDING":
        value["authority_ref"] = authority_ref
        value["evidence_refs"] = (
            ["evidence/review"] if evidence_refs is None else evidence_refs
        )
    return value


def node_decision(outcome: ReadyResolutionOutcome, node_id: str) -> dict[str, object]:
    assert outcome.result is not None
    return next(
        item
        for item in outcome.result["node_decisions"]
        if item["node_id"] == node_id
    )


def join_decision(outcome: ReadyResolutionOutcome, join_id: str) -> dict[str, object]:
    assert outcome.result is not None
    return next(
        item
        for item in outcome.result["join_decisions"]
        if item["join_id"] == join_id
    )


class ReadyResolverInterfaceAndDigestTests(unittest.TestCase):
    def test_internal_interface_types_and_success_error_exclusivity(self) -> None:
        self.assertTrue(hasattr(ReadyResolutionIssue, "__dataclass_fields__"))
        self.assertTrue(hasattr(ReadyResolutionOutcome, "__dataclass_fields__"))
        candidate_graph = graph()
        outcome = resolve_ready_nodes(candidate_graph, resolution_input(candidate_graph))
        self.assertIsNotNone(outcome.result)
        self.assertIsNone(outcome.error)
        with self.assertRaises(ValueError):
            ReadyResolutionOutcome(result={}, error={})
        with self.assertRaises(ValueError):
            ReadyResolutionOutcome(result=None, error=None)

    def test_fixed_input_digest_vector(self) -> None:
        candidate = {
            "schema_id": "urn:sagekit:ready-resolution:v1:input",
            "schema_version": 1,
            "graph_digest": "a" * 64,
            "graph_generation": 1,
            "node_states": [
                {
                    "node_id": "阶段/节点 α",
                    "status": "PENDING",
                    "evidence_refs": [],
                }
            ],
            "resource_availability": [
                {
                    "resource_id": "cpu.light",
                    "availability": "BUSY",
                    "reason_code": "RESOURCE_BUSY",
                    "evidence_refs": ["evidence/resource-snapshot"],
                }
            ],
            "external_join_decisions": [
                {
                    "join_id": "manual-review",
                    "decision": "SATISFIED",
                    "authority_ref": "authority/review-approval",
                    "evidence_refs": ["evidence/review-approval"],
                }
            ],
        }
        expected = hashlib.sha256(
            INPUT_DIGEST_DOMAIN + canonical_bytes(candidate)
        ).hexdigest()
        self.assertEqual(
            "70133af3c18e621a9f4586e43b8fe1807b5a0c85e4976eea302745ec1a8b0a37",
            expected,
        )
        self.assertEqual(expected, canonical_ready_input_digest(candidate))

    def test_input_ordering_does_not_change_digest_or_result(self) -> None:
        candidate_graph = graph(
            nodes=[node("a"), node("b")],
            joins=[
                {
                    "id": "gate",
                    "requires": ["a"],
                    "policy": "manual-gate",
                }
            ],
            human_gates=["gate"],
        )
        original = resolution_input(
            candidate_graph,
            node_states=[
                state("b"),
                state(
                    "a",
                    "NO_ACTION_REQUIRED",
                    evidence_refs=["evidence/z", "evidence/a"],
                ),
            ],
            resources=[
                resource("z", "UNKNOWN", evidence_refs=["evidence/z", "evidence/a"]),
                resource("a", "AVAILABLE"),
            ],
            external=[
                external(
                    "gate",
                    "SATISFIED",
                    evidence_refs=["evidence/z", "evidence/a"],
                )
            ],
        )
        reordered = copy.deepcopy(original)
        reordered["node_states"].reverse()
        reordered["resource_availability"].reverse()
        for collection in (
            reordered["node_states"],
            reordered["resource_availability"],
            reordered["external_join_decisions"],
        ):
            for item in collection:
                if "evidence_refs" in item:
                    item["evidence_refs"].reverse()
        self.assertEqual(
            canonical_ready_input_digest(original),
            canonical_ready_input_digest(reordered),
        )
        self.assertEqual(
            resolve_ready_nodes(candidate_graph, original),
            resolve_ready_nodes(candidate_graph, reordered),
        )

    def test_every_semantic_input_change_changes_digest(self) -> None:
        candidate = {
            "schema_id": "urn:sagekit:ready-resolution:v1:input",
            "schema_version": 1,
            "graph_digest": "a" * 64,
            "graph_generation": 1,
            "node_states": [
                {
                    "node_id": "node",
                    "status": "SUCCEEDED",
                    "result_digest": "node-result:a",
                    "evidence_refs": ["evidence/node"],
                }
            ],
            "resource_availability": [
                resource("cpu", "BUSY", evidence_refs=["evidence/resource"])
            ],
            "external_join_decisions": [
                external("gate", "SATISFIED", evidence_refs=["evidence/gate"])
            ],
        }
        baseline = canonical_ready_input_digest(candidate)
        mutations = [
            ("node_states", 0, "status", "FAILED"),
            ("node_states", 0, "result_digest", "node-result:b"),
            ("node_states", 0, "evidence_refs", ["evidence/other"]),
            ("resource_availability", 0, "availability", "UNKNOWN"),
            ("resource_availability", 0, "reason_code", "RESOURCE_UNKNOWN"),
            ("resource_availability", 0, "evidence_refs", ["evidence/other"]),
            ("external_join_decisions", 0, "decision", "REJECTED"),
            ("external_join_decisions", 0, "authority_ref", "authority/other"),
            ("external_join_decisions", 0, "evidence_refs", ["evidence/other"]),
        ]
        for collection, index, field, value in mutations:
            changed = copy.deepcopy(candidate)
            changed[collection][index][field] = value
            self.assertNotEqual(baseline, canonical_ready_input_digest(changed), field)

    def test_validate_input_reports_structural_and_identity_issues(self) -> None:
        malformed = {
            "schema_id": "wrong",
            "schema_version": True,
            "graph_digest": "not-a-digest",
            "graph_generation": 0,
            "node_states": [
                state("duplicate"),
                state("duplicate", "RUNNING"),
            ],
            "resource_availability": [],
            "external_join_decisions": [],
            "stdout": "restricted",
        }
        issues = validate_ready_resolution_input(malformed)
        self.assertTrue(issues)
        self.assertEqual(tuple(sorted(issues, key=lambda item: (item.path, item.code))), issues)
        self.assertIsNone(canonical_ready_input_digest(malformed))


class ReadyResolverNodeAndResourceTests(unittest.TestCase):
    def test_valid_independent_nodes_are_ready(self) -> None:
        candidate_graph = graph(nodes=[node("b"), node("a")])
        outcome = resolve_ready_nodes(candidate_graph, resolution_input(candidate_graph))
        self.assertIsNone(outcome.error)
        self.assertEqual(["a", "b"], [item["node_id"] for item in outcome.result["node_decisions"]])
        self.assertEqual(
            {"a": "READY", "b": "READY"},
            {
                item["node_id"]: item["disposition"]
                for item in outcome.result["node_decisions"]
            },
        )
        self.assertEqual("READY", outcome.result["graph_disposition"])

    def test_dependency_pending_failed_and_blocked(self) -> None:
        candidate_graph = graph(
            nodes=[
                node("pending"),
                node("failed"),
                node("blocked"),
                node("wait-pending", depends_on=["pending"]),
                node("wait-failed", depends_on=["failed"]),
                node("stop", depends_on=["blocked"]),
            ]
        )
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("pending"),
                    state("failed", "FAILED"),
                    state("blocked", "BLOCKED"),
                    state("wait-pending"),
                    state("wait-failed"),
                    state("stop"),
                ],
            ),
        )
        pending = node_decision(outcome, "wait-pending")
        failed = node_decision(outcome, "wait-failed")
        blocked = node_decision(outcome, "stop")
        self.assertEqual(("WAITING_DEPENDENCY", ["pending"]), (pending["disposition"], pending["blocking_node_ids"]))
        self.assertEqual(["DEPENDENCY_PENDING"], pending["reason_codes"])
        self.assertEqual(("WAITING_DEPENDENCY", ["failed"]), (failed["disposition"], failed["blocking_node_ids"]))
        self.assertEqual(["DEPENDENCY_FAILED"], failed["reason_codes"])
        self.assertEqual(("BLOCKED", ["blocked"]), (blocked["disposition"], blocked["blocking_node_ids"]))

    def test_blocked_dependency_preserves_every_unsatisfied_blocker(self) -> None:
        candidate_graph = graph(
            nodes=[
                node("blocked"),
                node("failed"),
                node("pending"),
                node(
                    "target",
                    depends_on=["blocked", "failed", "pending"],
                ),
            ]
        )
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("blocked", "BLOCKED"),
                    state("failed", "FAILED"),
                    state("pending"),
                    state("target"),
                ],
            ),
        )
        decision = node_decision(outcome, "target")
        self.assertEqual("BLOCKED", decision["disposition"])
        self.assertEqual(
            ["blocked", "failed", "pending"],
            decision["blocking_node_ids"],
        )

    def test_done_with_concerns_is_not_required_success(self) -> None:
        candidate_graph = graph(
            nodes=[node("review"), node("publish", depends_on=["review"])]
        )
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("review", "DONE_WITH_CONCERNS"),
                    state("publish"),
                ],
            ),
        )
        self.assertEqual("NEEDS_CORRECTION", node_decision(outcome, "review")["disposition"])
        dependent = node_decision(outcome, "publish")
        self.assertEqual("WAITING_DEPENDENCY", dependent["disposition"])
        self.assertEqual(["DEPENDENCY_FAILED"], dependent["reason_codes"])

    def test_no_action_required_requires_digest_and_evidence(self) -> None:
        candidate_graph = graph()
        valid = resolution_input(
            candidate_graph,
            node_states=[
                state(
                    "node-a",
                    "NO_ACTION_REQUIRED",
                    evidence_refs=["evidence/no-action"],
                )
            ],
        )
        outcome = resolve_ready_nodes(candidate_graph, valid)
        self.assertEqual("COMPLETED", node_decision(outcome, "node-a")["disposition"])
        invalid = copy.deepcopy(valid)
        invalid["node_states"][0]["evidence_refs"] = []
        failure = resolve_ready_nodes(candidate_graph, invalid)
        self.assertIsNone(failure.result)
        self.assertEqual("REQUIRED_INPUT_INVALID", failure.error["error_code"])

    def test_current_node_status_mapping(self) -> None:
        statuses = {
            "RUNNING": "IN_PROGRESS",
            "SUCCEEDED": "COMPLETED",
            "FAILED": "NEEDS_CORRECTION",
            "NEEDS_CORRECTION": "NEEDS_CORRECTION",
            "DONE_WITH_CONCERNS": "NEEDS_CORRECTION",
            "HANDOFF": "HANDOFF_REQUIRED",
            "BLOCKED": "BLOCKED",
            "CANCELLED": "CANCELLED",
        }
        for status, disposition in statuses.items():
            with self.subTest(status=status):
                candidate_graph = graph()
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(candidate_graph, node_states=[state("node-a", status)]),
                )
                self.assertEqual(disposition, node_decision(outcome, "node-a")["disposition"])

    def test_busy_unknown_and_missing_resources_wait(self) -> None:
        candidate_graph = graph(nodes=[node("work", resources=["busy", "unknown", "missing"])])
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                resources=[
                    resource("busy", "BUSY"),
                    resource("unknown", "UNKNOWN"),
                ],
            ),
        )
        decision = node_decision(outcome, "work")
        self.assertEqual("WAITING_RESOURCE", decision["disposition"])
        self.assertEqual(["busy", "missing", "unknown"], decision["blocking_resource_ids"])
        self.assertEqual(["RESOURCE_BUSY", "RESOURCE_UNKNOWN"], decision["reason_codes"])

    def test_unavailable_resource_blocks(self) -> None:
        candidate_graph = graph(nodes=[node("work", resources=["cpu"])])
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(candidate_graph, resources=[resource("cpu", "UNAVAILABLE")]),
        )
        decision = node_decision(outcome, "work")
        self.assertEqual("BLOCKED", decision["disposition"])
        self.assertEqual(["cpu"], decision["blocking_resource_ids"])
        self.assertEqual(["RESOURCE_UNAVAILABLE"], decision["reason_codes"])

    def test_unavailable_resource_preserves_every_non_available_blocker(self) -> None:
        candidate_graph = graph(
            nodes=[
                node(
                    "work",
                    resources=["unavailable", "busy", "unknown", "missing"],
                )
            ]
        )
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                resources=[
                    resource("unavailable", "UNAVAILABLE"),
                    resource("busy", "BUSY"),
                    resource("unknown", "UNKNOWN"),
                ],
            ),
        )
        decision = node_decision(outcome, "work")
        self.assertEqual("BLOCKED", decision["disposition"])
        self.assertEqual(
            ["busy", "missing", "unavailable", "unknown"],
            decision["blocking_resource_ids"],
        )

    def test_available_resources_allow_ready(self) -> None:
        candidate_graph = graph(nodes=[node("work", resources=["cpu"])])
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(candidate_graph, resources=[resource("cpu", "AVAILABLE")]),
        )
        decision = node_decision(outcome, "work")
        self.assertEqual("READY", decision["disposition"])
        self.assertEqual(
            ["DEPENDENCIES_SATISFIED", "RESOURCE_AVAILABLE"],
            decision["reason_codes"],
        )


class ReadyResolverJoinTests(unittest.TestCase):
    def test_all_required_waits_blocks_and_satisfies(self) -> None:
        candidate_graph = graph(
            nodes=[node("a"), node("b")],
            joins=[{"id": "all", "requires": ["a", "b"], "policy": "all-required"}],
        )
        cases = [
            (["SUCCEEDED", "PENDING"], "WAITING_NODE"),
            (["SUCCEEDED", "FAILED"], "BLOCKED"),
            (["SUCCEEDED", "SUCCEEDED"], "SATISFIED"),
        ]
        for statuses, disposition in cases:
            with self.subTest(disposition=disposition):
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(
                        candidate_graph,
                        node_states=[
                            state("a", statuses[0]),
                            state("b", statuses[1]),
                        ],
                    ),
                )
                self.assertEqual(disposition, join_decision(outcome, "all")["disposition"])

    def test_required_plus_optional_ignores_optional_for_closure(self) -> None:
        candidate_graph = graph(
            nodes=[node("required"), node("optional", classification="optional")],
            joins=[
                {
                    "id": "mixed",
                    "requires": ["required", "optional"],
                    "policy": "required-plus-optional",
                }
            ],
        )
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("required", "SUCCEEDED"),
                    state("optional", "FAILED"),
                ],
            ),
        )
        self.assertEqual("SATISFIED", join_decision(outcome, "mixed")["disposition"])
        self.assertEqual("NEEDS_CORRECTION", node_decision(outcome, "optional")["disposition"])

    def test_first_success_semantics(self) -> None:
        candidate_graph = graph(
            nodes=[
                node("a", classification="optional"),
                node("b", classification="optional"),
            ],
            joins=[
                {
                    "id": "first",
                    "requires": ["a", "b"],
                    "policy": "first-success",
                }
            ],
        )
        cases = [
            (["SUCCEEDED", "PENDING"], "SATISFIED"),
            (["FAILED", "PENDING"], "WAITING_NODE"),
            (["FAILED", "BLOCKED"], "BLOCKED"),
        ]
        for statuses, disposition in cases:
            with self.subTest(disposition=disposition):
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(
                        candidate_graph,
                        node_states=[
                            state("a", statuses[0]),
                            state("b", statuses[1]),
                        ],
                    ),
                )
                self.assertEqual(disposition, join_decision(outcome, "first")["disposition"])

    def test_manual_gate_pending_satisfied_and_rejected(self) -> None:
        self._assert_external_policy("manual-gate")

    def test_corrective_join_pending_satisfied_and_rejected(self) -> None:
        self._assert_external_policy("corrective-join")

    def _assert_external_policy(self, policy: str) -> None:
        candidate_graph = graph(
            nodes=[node("a")],
            joins=[{"id": "gate", "requires": ["a"], "policy": policy}],
            human_gates=["gate"] if policy == "manual-gate" else [],
        )
        for supplied, disposition in (
            ([], "REQUIRES_EXTERNAL_DECISION"),
            ([external("gate", "PENDING")], "REQUIRES_EXTERNAL_DECISION"),
            ([external("gate", "SATISFIED")], "SATISFIED"),
            ([external("gate", "REJECTED")], "REJECTED"),
        ):
            with self.subTest(policy=policy, disposition=disposition):
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(
                        candidate_graph,
                        node_states=[state("a", "SUCCEEDED")],
                        external=supplied,
                    ),
                )
                self.assertEqual(disposition, join_decision(outcome, "gate")["disposition"])

    def test_external_decision_cannot_bypass_prerequisites(self) -> None:
        candidate_graph = graph(
            nodes=[node("a")],
            joins=[{"id": "gate", "requires": ["a"], "policy": "manual-gate"}],
            human_gates=["gate"],
        )
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[state("a", "PENDING")],
                external=[external("gate", "SATISFIED")],
            ),
        )
        decision = join_decision(outcome, "gate")
        self.assertEqual("WAITING_NODE", decision["disposition"])
        self.assertEqual(["a"], decision["blocking_node_ids"])

    def test_blocked_join_preserves_failed_and_pending_prerequisites(self) -> None:
        for policy in ("all-required", "manual-gate", "corrective-join"):
            with self.subTest(policy=policy):
                candidate_graph = graph(
                    nodes=[node("blocked"), node("failed"), node("pending")],
                    joins=[
                        {
                            "id": "closure",
                            "requires": ["blocked", "failed", "pending"],
                            "policy": policy,
                        }
                    ],
                    human_gates=["closure"] if policy == "manual-gate" else [],
                )
                supplied = (
                    []
                    if policy == "all-required"
                    else [external("closure", "SATISFIED")]
                )
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(
                        candidate_graph,
                        node_states=[
                            state("blocked", "BLOCKED"),
                            state("failed", "FAILED"),
                            state("pending"),
                        ],
                        external=supplied,
                    ),
                )
                decision = join_decision(outcome, "closure")
                self.assertEqual("BLOCKED", decision["disposition"])
                self.assertEqual(
                    ["blocked", "failed", "pending"],
                    decision["blocking_node_ids"],
                )

    def test_external_decision_on_automatic_or_unknown_join_fails_closed(self) -> None:
        candidate_graph = graph(
            joins=[{"id": "automatic", "requires": ["node-a"], "policy": "all-required"}]
        )
        for join_id in ("automatic", "unknown"):
            with self.subTest(join_id=join_id):
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(
                        candidate_graph,
                        external=[external(join_id, "SATISFIED")],
                    ),
                )
                self.assertIsNone(outcome.result)
                self.assertEqual("REQUIRED_INPUT_INVALID", outcome.error["error_code"])

    def test_rejected_join_preserves_exact_101_reference_union(self) -> None:
        candidate_graph = graph(
            joins=[{"id": "gate", "requires": ["node-a"], "policy": "manual-gate"}],
            human_gates=["gate"],
        )
        evidence = [f"evidence/{index:03d}" for index in range(100)]
        outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[state("node-a", "SUCCEEDED")],
                external=[
                    external(
                        "gate",
                        "REJECTED",
                        authority_ref="authority/rejection",
                        evidence_refs=list(reversed(evidence)),
                    )
                ],
            ),
        )
        refs = join_decision(outcome, "gate")["blocking_refs"]
        self.assertEqual(101, len(refs))
        self.assertEqual({"authority/rejection", *evidence}, set(refs))
        self.assertNotIn("truncated", join_decision(outcome, "gate"))


class ReadyResolverBindingAndAdmissionTests(unittest.TestCase):
    def test_graph_digest_and_generation_binding_mismatch(self) -> None:
        candidate_graph = graph()
        candidate = resolution_input(candidate_graph)
        for field, value in (("graph_digest", "0" * 64), ("graph_generation", 2)):
            with self.subTest(field=field):
                changed = copy.deepcopy(candidate)
                changed[field] = value
                outcome = resolve_ready_nodes(candidate_graph, changed)
                self.assertEqual("GRAPH_BINDING_MISMATCH", outcome.error["error_code"])
                self.assertIsNone(outcome.result)

    def test_invalid_graph_is_graph_invalid(self) -> None:
        candidate_graph = graph()
        candidate = resolution_input(candidate_graph)
        candidate_graph["nodes"][0]["depends_on"] = ["missing"]
        outcome = resolve_ready_nodes(candidate_graph, candidate)
        self.assertEqual("GRAPH_INVALID", outcome.error["error_code"])

    def test_missing_unknown_and_duplicate_node_states_fail_closed(self) -> None:
        candidate_graph = graph(nodes=[node("a"), node("b")])
        cases = [
            [state("a")],
            [state("a"), state("b"), state("unknown")],
            [state("a"), state("a", "RUNNING"), state("b")],
        ]
        for states in cases:
            with self.subTest(states=states):
                outcome = resolve_ready_nodes(
                    candidate_graph,
                    resolution_input(candidate_graph, node_states=states),
                )
                self.assertEqual("REQUIRED_INPUT_INVALID", outcome.error["error_code"])
                self.assertIsNone(outcome.result)

    def test_input_canonical_oversize_returns_error_without_partial_result(self) -> None:
        oversized = {
            "schema_id": "urn:sagekit:ready-resolution:v1:input",
            "schema_version": 1,
            "graph_digest": "a" * 64,
            "graph_generation": 1,
            "node_states": [],
            "resource_availability": [],
            "external_join_decisions": [],
            "padding": "x" * (16 * 1024 * 1024),
        }
        outcome = resolve_ready_nodes(graph(), oversized)
        self.assertEqual("INPUT_TOO_LARGE", outcome.error["error_code"])
        self.assertIsNone(outcome.result)
        self.assertNotIn("node_decisions", outcome.error)

    def test_graph_byte_boundary_is_inclusive_and_plus_one_is_error(self) -> None:
        exact = graph()
        exact["graph_id"] = ""
        overhead = len(canonical_bytes(exact))
        exact["graph_id"] = "x" * (MAX_GRAPH_BYTES - overhead)
        self.assertEqual(MAX_GRAPH_BYTES, len(canonical_bytes(exact)))
        exact_input = resolution_input(exact)
        self.assertIsNotNone(resolve_ready_nodes(exact, exact_input).result)
        oversized = copy.deepcopy(exact)
        oversized["graph_id"] += "x"
        self.assertEqual(MAX_GRAPH_BYTES + 1, len(canonical_bytes(oversized)))
        outcome = resolve_ready_nodes(oversized, exact_input)
        self.assertEqual("GRAPH_TOO_LARGE", outcome.error["error_code"])
        self.assertIsNone(outcome.result)

    def test_nodes_and_joins_10000_boundary_and_plus_one(self) -> None:
        node_boundary = graph(nodes=[node(f"n-{index:05d}") for index in range(10000)])
        node_states = [state(f"n-{index:05d}", "BLOCKED") for index in range(10000)]
        node_outcome = resolve_ready_nodes(
            node_boundary,
            resolution_input(node_boundary, node_states=node_states),
        )
        self.assertIsNotNone(node_outcome.result)
        self.assertEqual(10000, len(node_outcome.result["node_decisions"]))

        node_over = graph(nodes=[node("a")] * 10001)
        node_error = resolve_ready_nodes(
            node_over,
            {
                **resolution_input(graph()),
                "node_states": [state("node-a")],
            },
        )
        self.assertEqual("RESOLUTION_LIMIT_EXCEEDED", node_error.error["error_code"])

        join_boundary = graph(
            joins=[
                {"id": f"j-{index:05d}", "requires": ["node-a"], "policy": "all-required"}
                for index in range(10000)
            ]
        )
        join_outcome = resolve_ready_nodes(
            join_boundary,
            resolution_input(join_boundary, node_states=[state("node-a", "SUCCEEDED")]),
        )
        self.assertIsNotNone(join_outcome.result)
        self.assertEqual(10000, len(join_outcome.result["join_decisions"]))

        join_over = graph(
            joins=[
                {"id": f"j-{index}", "requires": ["node-a"], "policy": "all-required"}
                for index in range(10001)
            ]
        )
        join_error = resolve_ready_nodes(
            join_over,
            {
                **resolution_input(graph()),
                "node_states": [state("node-a")],
            },
        )
        self.assertEqual("RESOLUTION_LIMIT_EXCEEDED", join_error.error["error_code"])

    def test_dependency_resource_and_requires_boundaries(self) -> None:
        exact_dependencies = graph(
            nodes=[
                {
                    **node("target"),
                    "depends_on": ["dependency"] * 10000,
                },
                node("dependency"),
            ]
        )
        exact_error = resolve_ready_nodes(
            exact_dependencies,
            {
                **resolution_input(graph()),
                "node_states": [state("node-a")],
            },
        )
        self.assertEqual("GRAPH_INVALID", exact_error.error["error_code"])
        exact_dependencies["nodes"][0]["depends_on"].append("dependency")
        over_error = resolve_ready_nodes(
            exact_dependencies,
            {
                **resolution_input(graph()),
                "node_states": [state("node-a")],
            },
        )
        self.assertEqual("RESOLUTION_LIMIT_EXCEEDED", over_error.error["error_code"])

        resource_ids = [f"resource-{index:05d}" for index in range(10000)]
        resource_boundary = graph(nodes=[node("target", resources=resource_ids)])
        resource_outcome = resolve_ready_nodes(
            resource_boundary,
            resolution_input(resource_boundary),
        )
        resource_decision = node_decision(resource_outcome, "target")
        self.assertEqual(10000, len(resource_decision["blocking_resource_ids"]))
        self.assertEqual(resource_ids, resource_decision["blocking_resource_ids"])
        resource_over = graph(nodes=[node("target", resources=resource_ids + ["over"])])
        resource_error = resolve_ready_nodes(
            resource_over,
            {
                **resolution_input(graph()),
                "node_states": [state("node-a")],
            },
        )
        self.assertEqual("RESOLUTION_LIMIT_EXCEEDED", resource_error.error["error_code"])

        required_ids = [f"required-{index:05d}" for index in range(10000)]
        requires_boundary = graph(
            nodes=[node(item) for item in required_ids],
            joins=[
                {"id": "closure", "requires": required_ids, "policy": "all-required"}
            ],
        )
        requires_outcome = resolve_ready_nodes(
            requires_boundary,
            resolution_input(
                requires_boundary,
                node_states=[state(item, "BLOCKED") for item in required_ids],
            ),
        )
        blockers = join_decision(requires_outcome, "closure")["blocking_node_ids"]
        self.assertEqual(10000, len(blockers))
        self.assertEqual(required_ids, blockers)
        requires_over = graph(
            joins=[
                {
                    "id": "closure",
                    "requires": ["node-a"] * 10001,
                    "policy": "all-required",
                }
            ]
        )
        requires_error = resolve_ready_nodes(
            requires_over,
            resolution_input(graph()),
        )
        self.assertEqual("RESOLUTION_LIMIT_EXCEEDED", requires_error.error["error_code"])

    def test_result_oversize_maps_to_error(self) -> None:
        candidate_graph = graph()
        with mock.patch("sagekit.ready_resolver.MAX_RESULT_CANONICAL_BYTES", 64):
            outcome = resolve_ready_nodes(
                candidate_graph,
                resolution_input(candidate_graph),
            )
        self.assertIsNone(outcome.result)
        self.assertEqual("RESULT_TOO_LARGE", outcome.error["error_code"])


class ReadyResolverDeterminismPrivacyAndDispositionTests(unittest.TestCase):
    def test_input_immutability_and_repeated_determinism(self) -> None:
        candidate_graph = graph(
            nodes=[node("b"), node("a", resources=["cpu"])],
        )
        candidate = resolution_input(
            candidate_graph,
            resources=[resource("cpu", "BUSY", evidence_refs=["evidence/z", "evidence/a"])],
        )
        graph_before = copy.deepcopy(candidate_graph)
        input_before = copy.deepcopy(candidate)
        first = resolve_ready_nodes(candidate_graph, candidate)
        second = resolve_ready_nodes(candidate_graph, candidate)
        self.assertEqual(first, second)
        self.assertEqual(graph_before, candidate_graph)
        self.assertEqual(input_before, candidate)

    def test_local_blocker_does_not_hide_independent_ready_or_running_work(self) -> None:
        candidate_graph = graph(nodes=[node("blocked"), node("independent")])
        ready_outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[state("blocked", "BLOCKED"), state("independent")],
            ),
        )
        self.assertEqual("READY", ready_outcome.result["graph_disposition"])
        running_outcome = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("blocked", "BLOCKED"),
                    state("independent", "RUNNING"),
                ],
            ),
        )
        self.assertEqual("IN_PROGRESS", running_outcome.result["graph_disposition"])

    def test_completion_is_fail_closed(self) -> None:
        candidate_graph = graph(
            nodes=[node("required"), node("optional", classification="optional")],
            joins=[
                {
                    "id": "gate",
                    "requires": ["required"],
                    "policy": "manual-gate",
                }
            ],
            human_gates=["gate"],
        )
        waiting = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("required", "SUCCEEDED"),
                    state("optional", "CANCELLED"),
                ],
            ),
        )
        self.assertEqual("WAITING", waiting.result["graph_disposition"])
        completed = resolve_ready_nodes(
            candidate_graph,
            resolution_input(
                candidate_graph,
                node_states=[
                    state("required", "SUCCEEDED"),
                    state("optional", "CANCELLED"),
                ],
                external=[external("gate", "SATISFIED")],
            ),
        )
        self.assertEqual("COMPLETED", completed.result["graph_disposition"])

    def test_opaque_unicode_slash_and_long_ids_are_preserved(self) -> None:
        opaque = " C:\\Looks\\Like\\Path/阶段/ß/" + ("长" * 4096)
        resource_id = "../资源/CPU"
        candidate_graph = graph(nodes=[node(opaque, resources=[resource_id])])
        candidate = resolution_input(
            candidate_graph,
            node_states=[state(opaque)],
            resources=[resource(resource_id, "UNAVAILABLE")],
        )
        before = copy.deepcopy(candidate)
        outcome = resolve_ready_nodes(candidate_graph, candidate)
        decision = node_decision(outcome, opaque)
        self.assertEqual(opaque, decision["node_id"])
        self.assertEqual([resource_id], decision["blocking_resource_ids"])
        self.assertEqual(before, candidate)

    def test_restricted_fields_and_private_reference_forms_are_rejected(self) -> None:
        candidate_graph = graph()
        base = resolution_input(candidate_graph)
        for field in (
            "prompt",
            "private_reasoning",
            "transcript",
            "stdout",
            "stderr",
            "credential",
            "secret",
            "process_handle",
            "payload",
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(base)
                changed[field] = "restricted"
                outcome = resolve_ready_nodes(candidate_graph, changed)
                self.assertEqual("REQUIRED_INPUT_INVALID", outcome.error["error_code"])
        for reference in (
            r"C:\private\approval",
            "/tmp/private",
            r"\\server\share",
            r"\rooted",
            "file:///private",
            "HTTPS://example.test/private",
            "evidence/line\nbreak",
        ):
            with self.subTest(reference=reference):
                changed = copy.deepcopy(base)
                changed["node_states"][0]["evidence_refs"] = [reference]
                outcome = resolve_ready_nodes(candidate_graph, changed)
                self.assertEqual("REQUIRED_INPUT_INVALID", outcome.error["error_code"])

    def test_output_contains_only_contract_fields(self) -> None:
        candidate_graph = graph()
        outcome = resolve_ready_nodes(candidate_graph, resolution_input(candidate_graph))
        self.assertEqual(
            {
                "schema_id",
                "schema_version",
                "graph_digest",
                "graph_generation",
                "input_digest",
                "graph_disposition",
                "node_decisions",
                "join_decisions",
                "summary",
            },
            set(outcome.result),
        )
        serialized = json.dumps(outcome.result, ensure_ascii=False).lower()
        for forbidden in (
            "private_reasoning",
            "transcript",
            "stdout",
            "stderr",
            "credential",
            "secret",
            "process_handle",
            "agent_handle",
            "tool_handle",
            "payload",
            "truncated",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_import_has_no_runtime_side_effects(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            env = {
                **os.environ,
                "PYTHONPATH": str(repository),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import socket\n"
                        "socket.socket=lambda *a,**k: (_ for _ in ()).throw("
                        "AssertionError('network access'))\n"
                        "import sagekit.ready_resolver\n"
                    ),
                ],
                cwd=directory,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual([], list(Path(directory).iterdir()))


if __name__ == "__main__":
    unittest.main()
