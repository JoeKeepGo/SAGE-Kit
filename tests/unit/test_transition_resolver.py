from __future__ import annotations

import copy
import importlib
import math
import os
from pathlib import Path
import socket
import subprocess
import threading
import unittest
from unittest import mock

import sagekit
import sagekit.graph_contract as graph_contract_owner
from sagekit.graph_contract import (
    NODE_STATUSES,
    canonical_graph_digest,
    validate_node_transition,
)
from sagekit.transition_resolver import (
    TransitionResolutionIssue,
    TransitionResolutionOutcome,
    canonical_node_result_digest,
    canonical_transition_input_digest,
    resolve_node_transition,
    validate_transition_resolution_input,
)


NODE_RESULT_VECTOR_SHA256 = (
    "bec9a2c92f462c99ee6a5389edf8a06cb2479433e89fd7286d8ea0702a90efb6"
)
TRANSITION_INPUT_VECTOR_SHA256 = (
    "e6ec15448d9c77ec74a77b430d9c7bfa2fd2b750c523f44fcfa1eafb3da1cd69"
)


def node(
    node_id: str,
    *,
    permission: str = "WRITE_AUTHORIZED",
    depends_on: list[str] | None = None,
    resources: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "role": "transition-resolution-vector",
        "depends_on": [] if depends_on is None else depends_on,
        "permission": permission,
        "verifier": "focused-transition-resolution-vector",
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": [] if resources is None else resources,
        "classification": "required",
    }


def graph(
    *,
    nodes: list[dict[str, object]] | None = None,
    joins: list[dict[str, object]] | None = None,
    graph_id: str = "graph/transition/α",
    generation: int = 7,
) -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": graph_id,
        "generation": generation,
        "source_authority": {
            "identity": "Stage 4C2 test authority",
            "reference": "transition-resolution/stage-4c2",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [node("node/α")] if nodes is None else nodes,
        "joins": [] if joins is None else joins,
    }


def node_result(
    node_id: str = "node/α",
    status: str = "SUCCEEDED",
    *,
    authority_change: bool = False,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_id": "urn:sagekit:graph-contract:v1:node-result",
        "schema_version": 1,
        "node_id": node_id,
        "status": status,
        "changed_paths": [],
        "evidence_refs": [],
        "findings": [],
        "authority_change": authority_change,
        "proposed_next_nodes": [],
    }
    if status == "NO_ACTION_REQUIRED":
        result.update(
            inspected_scope=["scope/α"],
            decision="No action was required.",
            evidence_refs=["evidence/α"],
        )
    if authority_change:
        result["decision"] = "Request an authority decision."
    return result


def transition_input(
    candidate_graph: dict[str, object],
    *,
    status: str = "SUCCEEDED",
    previous_status: str = "RUNNING",
    authority_change: bool = False,
) -> dict[str, object]:
    node_id = str(candidate_graph["nodes"][0]["id"])
    return {
        "schema_id": "urn:sagekit:transition-resolution:v1:input",
        "schema_version": 1,
        "graph_id": candidate_graph["graph_id"],
        "graph_generation": candidate_graph["generation"],
        "graph_digest": canonical_graph_digest(candidate_graph),
        "run_id": ".run/运行/001",
        "authority_id": "~authority/权限",
        "controller_id": "_controller/β",
        "node_id": node_id,
        "attempt_id": ".attempt/001",
        "state_revision": 3,
        "last_event_sequence": 9,
        "previous_status": previous_status,
        "node_result": node_result(
            node_id,
            status,
            authority_change=authority_change,
        ),
    }


def node_result_vector() -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:node-result",
        "schema_version": 1,
        "node_id": "./阶段/😀",
        "status": "DONE_WITH_CONCERNS",
        "changed_paths": ["src/z", "src/a"],
        "evidence_refs": ["evidence/β", "evidence/α"],
        "findings": [
            {
                "finding_id": "finding/😀",
                "severity": "P2",
                "summary": "Concern β",
                "evidence_refs": ["evidence/β"],
            }
        ],
        "authority_change": False,
        "proposed_next_nodes": ["节点/二", "节点/一"],
    }


def transition_input_vector() -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:transition-resolution:v1:input",
        "schema_version": 1,
        "graph_id": "../图/alpha",
        "graph_generation": 7,
        "graph_digest": "0123456789abcdef" * 4,
        "run_id": ".run/运行/001",
        "authority_id": "~authority/权限",
        "controller_id": "_controller/β",
        "node_id": "!node/𐀀/é",
        "attempt_id": ".attempt/001",
        "state_revision": 0,
        "last_event_sequence": 9,
        "previous_status": "RUNNING",
        "node_result": {
            "schema_id": "urn:sagekit:graph-contract:v1:node-result",
            "schema_version": 1,
            "node_id": "!node/𐀀/é",
            "status": "HANDOFF",
            "changed_paths": [],
            "evidence_refs": ["evidence/handoff"],
            "findings": [],
            "authority_change": True,
            "proposed_next_nodes": ["下一步/β", "下一步/α"],
            "decision": "Request authority without mutating the graph.",
        },
    }


def error_code(outcome: TransitionResolutionOutcome) -> str:
    assert outcome.error is not None
    return str(outcome.error["error_code"])


class TransitionResolverInterfaceAndDigestTests(unittest.TestCase):
    def test_internal_symbols_are_module_only_and_outcome_is_exclusive(self) -> None:
        self.assertTrue(TransitionResolutionIssue)
        self.assertFalse(hasattr(sagekit, "resolve_node_transition"))
        candidate_graph = graph()
        success = resolve_node_transition(
            candidate_graph,
            transition_input(candidate_graph),
        )
        failure = resolve_node_transition({}, {})
        self.assertTrue(success.succeeded)
        self.assertFalse(failure.succeeded)
        for result, error in (
            (None, None),
            ({"ok": True}, None),
            (None, {"error": True}),
            ({"ok": True}, {"error": True}),
        ):
            with self.subTest(result=result, error=error):
                with self.assertRaises(ValueError):
                    TransitionResolutionOutcome(result=result, error=error)

    def test_fixed_node_result_digest_vector(self) -> None:
        candidate_graph = graph(
            nodes=[
                node("./阶段/😀"),
                node("节点/二"),
                node("节点/一"),
            ]
        )
        self.assertEqual(
            NODE_RESULT_VECTOR_SHA256,
            canonical_node_result_digest(candidate_graph, node_result_vector()),
        )

    def test_node_result_digest_reuses_bounded_graph_admission(self) -> None:
        from sagekit import transition_resolver

        candidate_graph = graph(
            nodes=[
                node("./阶段/😀"),
                node("节点/二"),
                node("节点/一"),
            ]
        )
        payload = node_result_vector()

        with (
            mock.patch.object(
                transition_resolver,
                "MAX_GRAPH_CANONICAL_BYTES",
                1,
            ),
            mock.patch.object(
                transition_resolver,
                "validate_graph_contract",
                wraps=transition_resolver.validate_graph_contract,
            ) as validator,
        ):
            self.assertIsNone(
                canonical_node_result_digest(candidate_graph, payload)
            )
            validator.assert_not_called()

        with (
            mock.patch.object(
                transition_resolver,
                "MAX_GRAPH_NODES",
                2,
            ),
            mock.patch.object(
                transition_resolver,
                "validate_graph_contract",
                wraps=transition_resolver.validate_graph_contract,
            ) as validator,
        ):
            self.assertIsNone(
                canonical_node_result_digest(candidate_graph, payload)
            )
            validator.assert_not_called()

        graph_size = transition_resolver._canonical_json_size(
            candidate_graph,
            limit=transition_resolver.MAX_GRAPH_CANONICAL_BYTES,
        )
        with mock.patch.object(
            transition_resolver,
            "MAX_GRAPH_CANONICAL_BYTES",
            graph_size,
        ):
            self.assertEqual(
                NODE_RESULT_VECTOR_SHA256,
                canonical_node_result_digest(candidate_graph, payload),
            )

    def test_fixed_transition_input_digest_vector(self) -> None:
        from sagekit import transition_resolver

        self.assertEqual(
            TRANSITION_INPUT_VECTOR_SHA256,
            transition_resolver._canonical_transition_input_digest_raw(
                transition_input_vector()
            ),
        )

    def test_json_integer_equivalence_bool_and_non_integer_rejection(self) -> None:
        base = transition_input_vector()
        from sagekit import transition_resolver

        expected = transition_resolver._canonical_transition_input_digest_raw(base)
        for value in (0, 0.0, -0.0):
            with self.subTest(value=value):
                changed = copy.deepcopy(base)
                changed["state_revision"] = value
                self.assertEqual(
                    expected,
                    transition_resolver._canonical_transition_input_digest_raw(
                        changed
                    ),
                )
        for value in (True, False, 1.5, math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                changed = copy.deepcopy(base)
                changed["state_revision"] = value
                candidate_graph = graph()
                candidate = transition_input(candidate_graph)
                candidate["state_revision"] = value
                self.assertIsNone(
                    canonical_transition_input_digest(
                        candidate_graph,
                        candidate,
                    )
                )
        integer = copy.deepcopy(base)
        floating = copy.deepcopy(base)
        integer["last_event_sequence"] = 1
        floating["last_event_sequence"] = 1.0
        self.assertEqual(
            transition_resolver._canonical_transition_input_digest_raw(integer),
            transition_resolver._canonical_transition_input_digest_raw(floating),
        )

    def test_non_bmp_paired_surrogate_and_lone_surrogate_handling(self) -> None:
        scalar = node_result_vector()
        candidate_graph = graph(
            nodes=[
                node("./阶段/😀"),
                node("节点/二"),
                node("节点/一"),
            ]
        )
        paired = copy.deepcopy(scalar)
        paired["node_id"] = "./阶段/\ud83d\ude00"
        self.assertEqual(
            canonical_node_result_digest(candidate_graph, scalar),
            canonical_node_result_digest(candidate_graph, paired),
        )
        lone = copy.deepcopy(scalar)
        lone["node_id"] = "\ud800"
        self.assertIsNone(canonical_node_result_digest(candidate_graph, lone))

    def test_paired_surrogates_bind_as_the_same_unicode_scalar(self) -> None:
        scalar_graph = graph(
            graph_id="graph/😀",
            nodes=[node("node/😀")],
        )
        candidate = transition_input(scalar_graph)
        candidate["graph_id"] = "graph/\ud83d\ude00"
        candidate["node_id"] = "node/\ud83d\ude00"
        candidate["node_result"]["node_id"] = "node/\ud83d\ude00"

        outcome = resolve_node_transition(scalar_graph, candidate)

        self.assertTrue(outcome.succeeded)
        self.assertEqual("graph/😀", outcome.result["graph_id"])
        self.assertEqual("node/😀", outcome.result["node_id"])
        direct = copy.deepcopy(candidate["node_result"])
        direct["node_id"] = "node/😀"
        self.assertEqual(
            canonical_node_result_digest(scalar_graph, direct),
            canonical_node_result_digest(
                scalar_graph,
                candidate["node_result"],
            ),
        )

    def test_array_reordering_changes_content_digest(self) -> None:
        original = node_result_vector()
        reordered = copy.deepcopy(original)
        reordered["proposed_next_nodes"].reverse()
        candidate_graph = graph(
            nodes=[
                node("./阶段/😀"),
                node("节点/二"),
                node("节点/一"),
            ]
        )
        self.assertNotEqual(
            canonical_node_result_digest(candidate_graph, original),
            canonical_node_result_digest(candidate_graph, reordered),
        )


class TransitionResolverAdmissionAndValidationTests(unittest.TestCase):
    def test_graph_byte_boundary_is_inclusive_and_plus_one_is_graph_too_large(
        self,
    ) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        from sagekit import transition_resolver

        size = len(transition_resolver._canonical_json_bytes(candidate_graph))
        with mock.patch.object(
            transition_resolver, "MAX_GRAPH_CANONICAL_BYTES", size
        ):
            self.assertIsNotNone(
                resolve_node_transition(candidate_graph, candidate).result
            )
            oversized = copy.deepcopy(candidate_graph)
            oversized["graph_id"] = str(oversized["graph_id"]) + "x"
            outcome = resolve_node_transition(oversized, candidate)
            hostile = copy.deepcopy(candidate_graph)
            hostile["graph_id"] = ("x" * (size + 1)) + "\ud800"
            hostile_outcome = resolve_node_transition(hostile, candidate)
        self.assertEqual("GRAPH_TOO_LARGE", error_code(outcome))
        self.assertIsNone(outcome.result)
        self.assertEqual("GRAPH_TOO_LARGE", error_code(hostile_outcome))

    def test_canonical_integer_admission_ignores_runtime_digit_limit(self) -> None:
        from sagekit import transition_resolver

        huge_integer = 10**5000
        size = transition_resolver._canonical_json_size(
            {"value": huge_integer},
            limit=10000,
        )
        self.assertEqual(5011, size)
        encoded = transition_resolver._canonical_json_bytes(
            {"value": huge_integer}
        )
        self.assertEqual(size, len(encoded))
        candidate_graph = graph(generation=huge_integer)
        candidate = transition_input(candidate_graph)
        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertTrue(outcome.succeeded, outcome.error)
        self.assertEqual(huge_integer, outcome.result["graph_generation"])
        self.assertIsNotNone(canonical_transition_input_digest(candidate_graph, candidate))

    def test_unknown_non_string_key_never_invokes_user_dunder(self) -> None:
        class HostileKey:
            def __str__(self):
                raise AssertionError("__str__ must not run before strict JSON admission")

        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        candidate[HostileKey()] = "restricted"

        outcome = resolve_node_transition(candidate_graph, candidate)

        self.assertEqual("REQUIRED_INPUT_INVALID", error_code(outcome))
        self.assertEqual("STRICT_JSON_REQUIRED", outcome.error["issues"][0]["code"])

    def test_success_path_owner_validation_oracle_includes_outcome_rebind(
        self,
    ) -> None:
        from sagekit import transition_resolver

        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        owner_validation = graph_contract_owner.validate_graph_contract
        owner_calls: list[object] = []

        def counted_owner(payload: object):
            owner_calls.append(payload)
            return owner_validation(payload)

        with mock.patch.object(
            transition_resolver,
            "validate_graph_contract",
            side_effect=counted_owner,
        ), mock.patch.object(
            graph_contract_owner,
            "validate_graph_contract",
            side_effect=counted_owner,
        ), mock.patch.object(
            TransitionResolutionOutcome,
            "_from_validated_source",
            wraps=TransitionResolutionOutcome._from_validated_source,
        ) as rebound:
            outcome = resolve_node_transition(candidate_graph, candidate)

        self.assertTrue(outcome.succeeded, outcome.error)
        self.assertEqual(
            2,
            len(owner_calls),
            "Graph admission plus graph-aware Node Result validation are required",
        )
        self.assertEqual(1, rebound.call_count)

    def test_structural_cardinality_boundaries_are_inclusive(self) -> None:
        from sagekit import transition_resolver

        cases: list[tuple[str, dict[str, object], str]] = [
            (
                "MAX_GRAPH_NODES",
                graph(nodes=[node("a")]),
                "nodes",
            ),
            (
                "MAX_GRAPH_JOINS",
                graph(
                    joins=[
                        {"id": "join", "requires": ["node/α"], "policy": "all-required"}
                    ]
                ),
                "joins",
            ),
            (
                "MAX_NODE_DEPENDENCIES",
                graph(nodes=[node("target", depends_on=["dependency"]), node("dependency")]),
                "depends_on",
            ),
            (
                "MAX_NODE_RESOURCES",
                graph(nodes=[node("target", resources=["resource"])]),
                "resources",
            ),
            (
                "MAX_JOIN_REQUIRES",
                graph(
                    joins=[
                        {"id": "join", "requires": ["node/α"], "policy": "all-required"}
                    ]
                ),
                "requires",
            ),
        ]
        for constant, candidate_graph, collection in cases:
            with self.subTest(constant=constant):
                candidate = transition_input(candidate_graph)
                with mock.patch.object(transition_resolver, constant, 1):
                    boundary = resolve_node_transition(candidate_graph, candidate)
                    self.assertNotEqual(
                        "RESOLUTION_LIMIT_EXCEEDED",
                        error_code(boundary) if boundary.error else None,
                    )
                    oversized = copy.deepcopy(candidate_graph)
                    if collection in {"nodes", "joins"}:
                        oversized[collection].append(copy.deepcopy(oversized[collection][0]))
                    elif collection in {"depends_on", "resources"}:
                        oversized["nodes"][0][collection].append("overflow")
                    else:
                        oversized["joins"][0]["requires"].append("overflow")
                    outcome = resolve_node_transition(oversized, candidate)
                self.assertEqual("RESOLUTION_LIMIT_EXCEEDED", error_code(outcome))

    def test_invalid_graph_precedes_binding_mismatch(self) -> None:
        valid_graph = graph()
        candidate = transition_input(valid_graph)
        invalid_graph = copy.deepcopy(valid_graph)
        invalid_graph["nodes"][0]["depends_on"] = ["missing"]
        outcome = resolve_node_transition(invalid_graph, candidate)
        self.assertEqual("GRAPH_INVALID", error_code(outcome))

    def test_external_gate_successor_topology_is_graph_invalid(self) -> None:
        for policy in ("manual-gate", "corrective-join"):
            with self.subTest(policy=policy):
                candidate_graph = graph(
                    nodes=[
                        node("gate-prerequisite"),
                        node("post-gate", depends_on=["gate-prerequisite"]),
                    ],
                    joins=[
                        {
                            "id": "external-gate",
                            "requires": ["gate-prerequisite"],
                            "policy": policy,
                        }
                    ],
                )
                if policy == "manual-gate":
                    candidate_graph["human_gates"] = ["external-gate"]
                candidate = copy.deepcopy(candidate_graph)
                candidate["nodes"] = [node("gate-prerequisite")]
                candidate["joins"] = []
                resolution = transition_input(candidate)
                resolution["graph_id"] = candidate_graph["graph_id"]
                resolution["graph_generation"] = candidate_graph["generation"]
                resolution["graph_digest"] = "0" * 64

                outcome = resolve_node_transition(candidate_graph, resolution)

                self.assertIsNone(outcome.result)
                self.assertEqual("GRAPH_INVALID", error_code(outcome))

    def test_valid_graph_binding_mismatch(self) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        for field, value in (
            ("graph_id", "wrong"),
            ("graph_generation", 1),
            ("graph_digest", "0" * 64),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(candidate)
                changed[field] = value
                self.assertEqual(
                    "GRAPH_BINDING_MISMATCH",
                    error_code(resolve_node_transition(candidate_graph, changed)),
                )

    def test_input_missing_unknown_and_type_errors(self) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        variants = []
        missing = copy.deepcopy(candidate)
        del missing["attempt_id"]
        variants.append(missing)
        unknown = copy.deepcopy(candidate)
        unknown["prompt"] = "not allowed"
        variants.append(unknown)
        wrong_type = copy.deepcopy(candidate)
        wrong_type["state_revision"] = True
        variants.append(wrong_type)
        negative = copy.deepcopy(candidate)
        negative["last_event_sequence"] = -1
        variants.append(negative)
        for changed in variants:
            with self.subTest(changed=changed):
                outcome = resolve_node_transition(candidate_graph, changed)
                self.assertEqual("REQUIRED_INPUT_INVALID", error_code(outcome))
                self.assertIsNone(outcome.result)
        issues = validate_transition_resolution_input(candidate_graph, unknown)
        self.assertTrue(issues)
        self.assertTrue(all(isinstance(issue, TransitionResolutionIssue) for issue in issues))

    def test_input_byte_boundary_and_plus_one(self) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        from sagekit import transition_resolver

        size = len(transition_resolver._canonical_json_bytes(candidate))
        with mock.patch.object(
            transition_resolver, "MAX_INPUT_CANONICAL_BYTES", size
        ):
            self.assertIsNotNone(
                resolve_node_transition(candidate_graph, candidate).result
            )
            oversized = copy.deepcopy(candidate)
            oversized["attempt_id"] = str(oversized["attempt_id"]) + "x"
            self.assertIsNone(
                canonical_transition_input_digest(candidate_graph, oversized)
            )
            outcome = resolve_node_transition(candidate_graph, oversized)
        self.assertEqual("INPUT_TOO_LARGE", error_code(outcome))

    def test_input_admission_is_iterative_and_precedes_normalization(self) -> None:
        from sagekit import transition_resolver

        candidate_graph = graph()
        deeply_unknown: dict[str, object] = {}
        cursor = deeply_unknown
        for _ in range(1100):
            child: dict[str, object] = {}
            cursor["nested"] = child
            cursor = child
        candidate = transition_input(candidate_graph)
        candidate["node_result"]["unknown_deep"] = deeply_unknown

        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertEqual("NODE_RESULT_INVALID", error_code(outcome))

        valid = transition_input(candidate_graph)
        size = transition_resolver._canonical_json_size(
            valid,
            limit=transition_resolver.MAX_INPUT_CANONICAL_BYTES,
        )
        oversized = copy.deepcopy(valid)
        oversized["attempt_id"] = str(oversized["attempt_id"]) + "x"
        with (
            mock.patch.object(
                transition_resolver,
                "MAX_INPUT_CANONICAL_BYTES",
                size,
            ),
            mock.patch.object(
                transition_resolver,
                "_normalize_json_value",
                side_effect=AssertionError("recursive normalization used"),
            ),
        ):
            outcome = resolve_node_transition(candidate_graph, oversized)
        self.assertEqual("INPUT_TOO_LARGE", error_code(outcome))

    def test_node_result_digest_is_graph_aware_iterative_and_bounded(self) -> None:
        from sagekit import transition_resolver

        candidate_graph = graph()
        payload = node_result()
        expected = canonical_node_result_digest(candidate_graph, payload)
        self.assertIsNotNone(expected)
        invalid_graph = copy.deepcopy(candidate_graph)
        invalid_graph["unknown"] = True
        self.assertIsNone(canonical_node_result_digest(invalid_graph, payload))

        read_only_graph = graph(
            nodes=[node("node/α", permission="READ_ONLY_REVIEW")]
        )
        changed = node_result()
        changed["changed_paths"] = ["src/forbidden.py"]
        self.assertIsNone(
            canonical_node_result_digest(read_only_graph, changed)
        )

        size = transition_resolver._canonical_json_size(
            payload,
            limit=transition_resolver.MAX_INPUT_CANONICAL_BYTES,
        )
        with (
            mock.patch.object(
                transition_resolver,
                "_canonical_json_bytes",
                side_effect=AssertionError("digest materialized bytes"),
            ),
            mock.patch.object(
                transition_resolver,
                "MAX_INPUT_CANONICAL_BYTES",
                size,
            ),
        ):
            self.assertEqual(
                expected,
                canonical_node_result_digest(candidate_graph, payload),
            )
        with mock.patch.object(
            transition_resolver,
            "MAX_INPUT_CANONICAL_BYTES",
            size - 1,
        ):
            self.assertIsNone(
                canonical_node_result_digest(candidate_graph, payload)
            )

    def test_node_binding_mismatch(self) -> None:
        candidate_graph = graph(nodes=[node("node/α"), node("node/β")])
        candidate = transition_input(candidate_graph)
        candidate["node_result"]["node_id"] = "node/β"
        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertEqual("NODE_BINDING_MISMATCH", error_code(outcome))

    def test_invalid_node_result_and_graph_aware_rules(self) -> None:
        candidate_graph = graph(nodes=[node("node/α", permission="READ_ONLY_REVIEW")])
        candidate = transition_input(candidate_graph)
        invalid = copy.deepcopy(candidate)
        invalid["node_result"]["changed_paths"] = ["src/changed.py"]
        self.assertIsNone(
            canonical_node_result_digest(
                candidate_graph,
                invalid["node_result"],
            )
        )
        self.assertIsNone(
            canonical_transition_input_digest(candidate_graph, invalid)
        )
        self.assertEqual(
            "NODE_RESULT_INVALID",
            error_code(resolve_node_transition(candidate_graph, invalid)),
        )
        unknown = copy.deepcopy(candidate)
        unknown["node_result"]["proposed_next_nodes"] = ["unknown"]
        self.assertIsNone(
            canonical_node_result_digest(
                candidate_graph,
                unknown["node_result"],
            )
        )
        self.assertIsNone(
            canonical_transition_input_digest(candidate_graph, unknown)
        )
        self.assertEqual(
            "NODE_RESULT_INVALID",
            error_code(resolve_node_transition(candidate_graph, unknown)),
        )
        malformed = copy.deepcopy(candidate)
        malformed["node_result"]["findings"] = "not-an-array"
        self.assertEqual(
            "NODE_RESULT_INVALID",
            error_code(resolve_node_transition(candidate_graph, malformed)),
        )


class TransitionResolverSemanticsTests(unittest.TestCase):
    def test_complete_allowed_transition_table_is_reused(self) -> None:
        candidate_graph = graph()
        for previous in sorted(NODE_STATUSES):
            for proposed in sorted(NODE_STATUSES):
                with self.subTest(previous=previous, proposed=proposed):
                    candidate = transition_input(
                        candidate_graph,
                        status=proposed,
                        previous_status=previous,
                    )
                    outcome = resolve_node_transition(candidate_graph, candidate)
                    expected = validate_node_transition(previous, proposed).allowed
                    self.assertEqual(expected, outcome.succeeded)
                    if not expected:
                        self.assertEqual("TRANSITION_NOT_ALLOWED", error_code(outcome))

    def test_disallowed_and_terminal_transitions(self) -> None:
        candidate_graph = graph()
        disallowed = transition_input(
            candidate_graph,
            status="PENDING",
            previous_status="RUNNING",
        )
        terminal = transition_input(
            candidate_graph,
            status="SUCCEEDED",
            previous_status="SUCCEEDED",
        )
        for candidate in (disallowed, terminal):
            with self.subTest(candidate=candidate):
                self.assertEqual(
                    "TRANSITION_NOT_ALLOWED",
                    error_code(resolve_node_transition(candidate_graph, candidate)),
                )

    def test_distinct_no_action_and_done_with_concerns_are_preserved(self) -> None:
        candidate_graph = graph()
        for status in ("NO_ACTION_REQUIRED", "DONE_WITH_CONCERNS"):
            with self.subTest(status=status):
                outcome = resolve_node_transition(
                    candidate_graph,
                    transition_input(candidate_graph, status=status),
                )
                self.assertEqual(status, outcome.result["next_status"])
                self.assertNotEqual("SUCCEEDED", outcome.result["next_status"])

    def test_ordinary_apply_result_binds_snapshot_and_grants_nothing(self) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertIsNone(outcome.error)
        result = outcome.result
        assert result is not None
        self.assertEqual("APPLY_TRANSITION", result["disposition"])
        self.assertEqual("SUCCEEDED", result["next_status"])
        self.assertEqual("NODE_RESULT_STATUS_APPLIED", result["reason_code"])
        self.assertFalse(result["authority_decision_required"])
        self.assertTrue(result["transition_allowed"])
        self.assertEqual(
            canonical_transition_input_digest(candidate_graph, candidate),
            result["input_digest"],
        )
        self.assertEqual(
            canonical_node_result_digest(
                candidate_graph,
                candidate["node_result"],
            ),
            result["node_result_digest"],
        )
        for field in (
            "graph_id",
            "graph_generation",
            "graph_digest",
            "run_id",
            "authority_id",
            "controller_id",
            "node_id",
            "attempt_id",
            "state_revision",
            "last_event_sequence",
            "previous_status",
        ):
            self.assertEqual(candidate[field], result[field])
        for field in (
            "grants_execution_authority",
            "grants_graph_mutation_authority",
            "grants_gate_authority",
            "grants_write_authority",
        ):
            self.assertIs(False, result[field])

    def test_authority_handoff_result_and_false_green_rejection(self) -> None:
        candidate_graph = graph()
        handoff = transition_input(
            candidate_graph,
            status="HANDOFF",
            authority_change=True,
        )
        outcome = resolve_node_transition(candidate_graph, handoff)
        self.assertEqual(
            "APPLY_HANDOFF_AND_REQUEST_AUTHORITY",
            outcome.result["disposition"],
        )
        self.assertEqual("HANDOFF", outcome.result["next_status"])
        self.assertEqual(
            "AUTHORITY_CHANGE_HANDOFF_REQUIRED",
            outcome.result["reason_code"],
        )
        self.assertTrue(outcome.result["authority_decision_required"])
        for status in (
            "SUCCEEDED",
            "NO_ACTION_REQUIRED",
            "DONE_WITH_CONCERNS",
        ):
            with self.subTest(status=status):
                candidate = transition_input(
                    candidate_graph,
                    status=status,
                    authority_change=True,
                )
                self.assertEqual(
                    "AUTHORITY_CHANGE_STATUS_INVALID",
                    error_code(resolve_node_transition(candidate_graph, candidate)),
                )
        missing_decision = transition_input(
            candidate_graph,
            status="SUCCEEDED",
            authority_change=True,
        )
        del missing_decision["node_result"]["decision"]
        self.assertEqual(
            "NODE_RESULT_INVALID",
            error_code(resolve_node_transition(candidate_graph, missing_decision)),
        )

    def test_result_oversize_is_error_without_partial_result(self) -> None:
        candidate_graph = graph()
        from sagekit import transition_resolver

        with mock.patch.object(transition_resolver, "MAX_RESULT_CANONICAL_BYTES", 1):
            outcome = resolve_node_transition(
                candidate_graph,
                transition_input(candidate_graph),
            )
        self.assertEqual("RESULT_TOO_LARGE", error_code(outcome))
        self.assertIsNone(outcome.result)
        self.assertNotIn("next_status", outcome.error)

    def test_proposed_nodes_are_digest_bound_without_execution_effect(self) -> None:
        candidate_graph = graph(nodes=[node("node/α"), node("node/β")])
        candidate = transition_input(candidate_graph)
        candidate["node_result"]["proposed_next_nodes"] = ["node/β"]
        before_graph = copy.deepcopy(candidate_graph)
        before_input = copy.deepcopy(candidate)
        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertEqual(before_graph, candidate_graph)
        self.assertEqual(before_input, candidate)
        self.assertNotIn("proposed_next_nodes", outcome.result)
        self.assertFalse(outcome.result["grants_graph_mutation_authority"])


class TransitionResolverDeterminismAndPurityTests(unittest.TestCase):
    def test_issue_count_is_bounded_ordered_and_deterministic(self) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        for index in range(150):
            candidate[f"unknown_{index:03d}"] = "restricted"
        first = resolve_node_transition(candidate_graph, candidate)
        second = resolve_node_transition(candidate_graph, candidate)
        self.assertEqual(first, second)
        issues = first.error["issues"]
        self.assertGreaterEqual(len(issues), 1)
        self.assertLessEqual(len(issues), 100)
        triples = [
            (item["path"], item["code"], item["message"]) for item in issues
        ]
        self.assertEqual(sorted(triples), triples)

    def test_opaque_unicode_slash_long_identities_are_preserved(self) -> None:
        opaque = " C:\\Looks\\Like\\Path/阶段/😀/" + ("长" * 1024)
        candidate_graph = graph(nodes=[node(opaque)], graph_id="../图/alpha")
        candidate = transition_input(candidate_graph)
        for field in (
            "run_id",
            "authority_id",
            "controller_id",
            "attempt_id",
        ):
            candidate[field] = opaque
        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertIsNotNone(outcome.result)
        self.assertEqual(opaque, outcome.result["node_id"])
        for field in ("run_id", "authority_id", "controller_id", "attempt_id"):
            self.assertEqual(opaque, outcome.result[field])

    def test_input_immutability_and_repeated_call_determinism(self) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        before_graph = copy.deepcopy(candidate_graph)
        before_input = copy.deepcopy(candidate)
        first = resolve_node_transition(candidate_graph, candidate)
        second = resolve_node_transition(candidate_graph, candidate)
        self.assertEqual(first, second)
        self.assertEqual(before_graph, candidate_graph)
        self.assertEqual(before_input, candidate)

    def test_outcome_rejects_forgery_and_returns_defensive_copies(self) -> None:
        from sagekit import transition_resolver

        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertTrue(outcome.succeeded)
        original = outcome.result
        assert original is not None

        forged = copy.deepcopy(original)
        forged["input_digest"] = "0" * 64
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome(result=forged, error=None)
        self.assertFalse(hasattr(TransitionResolutionOutcome, "_from_result"))
        self.assertFalse(hasattr(transition_resolver, "_OUTCOME_FACTORY_TOKEN"))
        self.assertFalse(hasattr(transition_resolver, "_outcome"))
        with self.assertRaises(AttributeError):
            outcome._result_snapshot = {}
        with self.assertRaises(AttributeError):
            del outcome._result_snapshot

        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                candidate,
                forged,
            )
        forged = copy.deepcopy(original)
        forged["grants_write_authority"] = True
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                candidate,
                forged,
            )
        forged = copy.deepcopy(original)
        forged["node_result_digest"] = "0" * 64
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                candidate,
                forged,
            )
        forged = copy.deepcopy(original)
        forged["schema_version"] = True
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                candidate,
                forged,
            )

        fabricated_source = transition_resolver._AdmittedTransitionSource(
            graph_snapshot=transition_resolver._freeze_json(candidate_graph),
            input_snapshot=transition_resolver._freeze_json(candidate),
            normalized_input_snapshot=transition_resolver._freeze_json(
                transition_resolver._transition_input_identity_view(candidate)
            ),
            graph_digest=str(candidate["graph_digest"]),
        )
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                candidate,
                copy.deepcopy(original),
                _admitted_source=fabricated_source,
            )

        changed_input = copy.deepcopy(candidate)
        changed_input["state_revision"] = 4
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                changed_input,
                copy.deepcopy(original),
            )
        changed_node_result = copy.deepcopy(candidate)
        changed_node_result["node_result"]["evidence_refs"].append("evidence/new")
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                candidate_graph,
                changed_node_result,
                copy.deepcopy(original),
            )
        changed_graph = copy.deepcopy(candidate_graph)
        changed_graph["source_authority"]["reference"] = "changed/source"
        graph_bound_input = copy.deepcopy(candidate)
        graph_bound_input["graph_digest"] = canonical_graph_digest(changed_graph)
        with self.assertRaises(ValueError):
            TransitionResolutionOutcome._from_validated_source(
                changed_graph,
                graph_bound_input,
                copy.deepcopy(original),
            )

        rebuilt = TransitionResolutionOutcome._from_validated_source(
            candidate_graph,
            candidate,
            copy.deepcopy(original),
        )
        self.assertTrue(rebuilt.succeeded)
        self.assertEqual(original, rebuilt.result)

        original["input_digest"] = "0" * 64
        original["grants_write_authority"] = True
        rebound = outcome.result
        assert rebound is not None
        self.assertNotEqual("0" * 64, rebound["input_digest"])
        self.assertFalse(rebound["grants_write_authority"])
        self.assertTrue(outcome.succeeded)

        failed = resolve_node_transition({}, {})
        error_copy = failed.error
        assert error_copy is not None
        error_copy["error_code"] = "RESULT_TOO_LARGE"
        self.assertNotEqual("RESULT_TOO_LARGE", failed.error["error_code"])

    def test_import_has_no_workspace_side_effects(self) -> None:
        import sagekit.transition_resolver as module

        original_cwd = Path.cwd()
        temporary = original_cwd / ".transition-resolver-import-probe"
        self.assertFalse(temporary.exists())
        before = set(original_cwd.iterdir())
        importlib.reload(module)
        self.assertEqual(before, set(original_cwd.iterdir()))
        self.assertFalse(temporary.exists())

    def test_resolution_does_not_access_filesystem_network_runtime_or_processes(
        self,
    ) -> None:
        candidate_graph = graph()
        candidate = transition_input(candidate_graph)
        denied = AssertionError("side effect attempted")
        with (
            mock.patch("builtins.open", side_effect=denied),
            mock.patch.object(Path, "open", side_effect=denied),
            mock.patch.object(Path, "read_text", side_effect=denied),
            mock.patch.object(Path, "write_text", side_effect=denied),
            mock.patch.object(socket, "socket", side_effect=denied),
            mock.patch.object(subprocess, "Popen", side_effect=denied),
            mock.patch.object(threading, "Thread", side_effect=denied),
            mock.patch.object(os, "getenv", side_effect=denied),
        ):
            outcome = resolve_node_transition(candidate_graph, candidate)
        self.assertIsNotNone(outcome.result)


if __name__ == "__main__":
    unittest.main()
