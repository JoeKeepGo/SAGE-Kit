import copy
import json
import unittest
from pathlib import Path

import sagekit.graph_contract as graph_contract
from sagekit.graph_contract import (
    GraphContractError,
    GraphValidationIssue,
    GraphValidationResult,
    NodeTransitionResult,
    canonical_graph_digest,
    validate_graph_contract,
    validate_node_result,
    validate_node_transition,
)


REPOSITORY = Path(__file__).resolve().parents[2]
GRAPH_SCHEMA = REPOSITORY / "docs/contracts/graph/v1/graph.schema.json"
NODE_RESULT_SCHEMA = REPOSITORY / "docs/contracts/graph/v1/node-result.schema.json"


def node(
    node_id,
    *,
    role="implementation",
    depends_on=None,
    permission="WRITE_AUTHORIZED",
    verifier="focused-tests",
    resources=None,
    classification="required",
):
    return {
        "id": node_id,
        "role": role,
        "depends_on": list(depends_on or []),
        "permission": permission,
        "verifier": verifier,
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": list(resources or []),
        "classification": classification,
    }


def minimal_graph():
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph-1",
        "generation": 1,
        "source_authority": {
            "identity": "accepted-authority",
            "reference": "docs/authority.md#graph",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [node("build")],
        "joins": [
            {
                "id": "complete",
                "requires": ["build"],
                "policy": "all-required",
            }
        ],
    }


def minimal_result(status="SUCCEEDED"):
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:node-result",
        "schema_version": 1,
        "node_id": "build",
        "status": status,
        "changed_paths": ["sagekit/graph_contract.py"],
        "evidence_refs": ["tests:focused"],
        "findings": [],
        "authority_change": False,
        "proposed_next_nodes": [],
    }


def issue_codes(result):
    return {issue.code for issue in result.issues}


class GraphStructuralValidationTests(unittest.TestCase):
    def test_valid_minimal_graph_has_digest_and_typed_result(self):
        payload = minimal_graph()
        result = validate_graph_contract(payload)
        self.assertIsInstance(result, GraphValidationResult)
        self.assertTrue(result.valid, result.to_json())
        self.assertEqual((), result.issues)
        self.assertRegex(result.semantic_digest or "", r"^[0-9a-f]{64}$")
        self.assertEqual(result.semantic_digest, canonical_graph_digest(payload))

    def test_unknown_fields_and_type_errors_fail_closed(self):
        payload = minimal_graph()
        payload["unexpected"] = True
        payload["nodes"][0]["also_unexpected"] = "x"
        payload["human_gates"] = "gate"
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertTrue(
            {"unknown-field", "invalid-type"}.issubset(issue_codes(result)),
            result.to_json(),
        )
        self.assertIsNone(result.semantic_digest)

    def test_bool_cannot_masquerade_as_integer(self):
        payload = minimal_graph()
        payload["generation"] = True
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("invalid-type", issue_codes(result))

    def test_json_primitive_subclasses_are_rejected(self):
        class StringSubclass(str):
            pass

        payload = minimal_graph()
        payload["schema_id"] = StringSubclass(payload["schema_id"])
        payload["nodes"][0]["role"] = StringSubclass("implementation")
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("invalid-type", issue_codes(result))

    def test_duplicate_node_and_join_ids_are_rejected(self):
        payload = minimal_graph()
        payload["nodes"].append(node("build"))
        payload["joins"].append(
            {"id": "complete", "requires": ["build"], "policy": "all-required"}
        )
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertTrue(
            {"duplicate-node-id", "duplicate-join-id"}.issubset(issue_codes(result)),
            result.to_json(),
        )

    def test_missing_dependency_and_join_references_are_rejected(self):
        payload = minimal_graph()
        payload["nodes"][0]["depends_on"] = ["missing-dependency"]
        payload["joins"][0]["requires"] = ["missing-join-node"]
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertTrue(
            {"missing-dependency", "missing-join-reference"}.issubset(
                issue_codes(result)
            ),
            result.to_json(),
        )

    def test_self_cycle_and_multi_node_cycle_are_detected(self):
        self_cycle = minimal_graph()
        self_cycle["nodes"][0]["depends_on"] = ["build"]
        self_result = validate_graph_contract(self_cycle)
        self.assertFalse(self_result.valid)
        self.assertTrue(
            {"self-dependency", "dependency-cycle"} & issue_codes(self_result),
            self_result.to_json(),
        )

        multi_cycle = minimal_graph()
        multi_cycle["nodes"] = [
            node("a", depends_on=["b"]),
            node("b", depends_on=["c"]),
            node("c", depends_on=["a"]),
        ]
        multi_cycle["joins"][0]["requires"] = ["a", "b", "c"]
        multi_result = validate_graph_contract(multi_cycle)
        self.assertFalse(multi_result.valid)
        self.assertIn("dependency-cycle", issue_codes(multi_result))

    def test_node_order_does_not_change_validity_or_digest(self):
        left = minimal_graph()
        left["human_gates"] = ["gate-b", "gate-a"]
        left["nodes"] = [
            node("a", resources=["resource-b", "resource-a"]),
            node("b", depends_on=["a"]),
        ]
        left["joins"][0]["requires"] = ["b", "a"]
        right = copy.deepcopy(left)
        right["human_gates"].reverse()
        right["nodes"].reverse()
        right["nodes"][0]["depends_on"].reverse()
        right["nodes"][1]["resources"].reverse()
        right["joins"][0]["requires"].reverse()
        self.assertTrue(validate_graph_contract(left).valid)
        self.assertTrue(validate_graph_contract(right).valid)
        self.assertEqual(
            canonical_graph_digest(left),
            canonical_graph_digest(right),
        )

    def test_invalid_graph_digest_raises_without_payload_copy(self):
        payload = minimal_graph()
        payload["generation"] = 0
        with self.assertRaises(GraphContractError) as caught:
            canonical_graph_digest(payload)
        self.assertNotIn(json.dumps(payload), str(caught.exception))


class GraphIdentityTests(unittest.TestCase):
    def test_semantic_field_changes_change_digest(self):
        original = minimal_graph()
        mutations = []
        changed = copy.deepcopy(original)
        changed["graph_id"] = "graph-2"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["generation"] = 2
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["source_authority"]["identity"] = "different-authority"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["governance_level"] = "Heavy"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["autonomy_level"] = "goal-based"
        changed["completion_verifier"] = "external-completion"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["human_gates"] = ["human-approval"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["nodes"][0]["role"] = "different-role"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["joins"][0]["id"] = "different-join"
        mutations.append(changed)
        baseline = canonical_graph_digest(original)
        for payload in mutations:
            with self.subTest(payload=payload):
                self.assertNotEqual(baseline, canonical_graph_digest(payload))

    def test_relocated_authority_reference_does_not_change_digest(self):
        left = minimal_graph()
        right = copy.deepcopy(left)
        right["source_authority"]["reference"] = (
            "D:/relocated/repository/docs/authority.md#graph"
        )
        self.assertEqual(
            canonical_graph_digest(left),
            canonical_graph_digest(right),
        )

    def test_authority_identity_change_changes_digest(self):
        left = minimal_graph()
        right = copy.deepcopy(left)
        right["source_authority"]["identity"] = "other-authority"
        self.assertNotEqual(
            canonical_graph_digest(left),
            canonical_graph_digest(right),
        )

    def test_authority_record_fragment_change_changes_digest(self):
        left = minimal_graph()
        right = copy.deepcopy(left)
        right["source_authority"]["reference"] = "docs/authority.md#other-record"
        self.assertNotEqual(
            canonical_graph_digest(left),
            canonical_graph_digest(right),
        )


class JoinValidationTests(unittest.TestCase):
    def test_safe_first_success_accepts_only_equivalent_read_only_optional_nodes(self):
        payload = minimal_graph()
        payload["nodes"] = [
            node(
                "review-a",
                role="redundant exploration",
                permission="READ_ONLY_REVIEW",
                resources=["source"],
                classification="optional",
            ),
            node(
                "review-b",
                role="redundant exploration",
                permission="READ_ONLY_REVIEW",
                resources=["source"],
                classification="optional",
            ),
        ]
        payload["joins"] = [
            {
                "id": "exploration",
                "requires": ["review-a", "review-b"],
                "policy": "first-success",
            }
        ]
        self.assertTrue(validate_graph_contract(payload).valid)

    def test_first_success_fails_closed_on_unsafe_nodes_or_equivalence(self):
        base = minimal_graph()
        base["nodes"] = [
            node(
                "a",
                role="redundant exploration",
                permission="READ_ONLY_REVIEW",
                classification="optional",
            ),
            node(
                "b",
                role="redundant exploration",
                permission="READ_ONLY_REVIEW",
                classification="optional",
            ),
        ]
        base["joins"] = [
            {
                "id": "exploration",
                "requires": ["a", "b"],
                "policy": "first-success",
            }
        ]
        mutations = []
        for key, value in (
            ("classification", "required"),
            ("permission", "WRITE_AUTHORIZED"),
            ("role", "different role"),
            ("verifier", "different verifier"),
            ("output_contract", "different-contract"),
        ):
            changed = copy.deepcopy(base)
            changed["nodes"][1][key] = value
            mutations.append(changed)
        changed = copy.deepcopy(base)
        changed["nodes"][1]["depends_on"] = ["a"]
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed["nodes"][1]["resources"] = ["different"]
        mutations.append(changed)
        for payload in mutations:
            with self.subTest(payload=payload):
                result = validate_graph_contract(payload)
                self.assertFalse(result.valid)
                self.assertTrue(
                    any(code.startswith("unsafe-first-success") for code in issue_codes(result)),
                    result.to_json(),
                )

    def test_first_success_requires_redundant_nodes(self):
        payload = minimal_graph()
        payload["nodes"] = [
            node(
                "only",
                role="redundant exploration",
                permission="READ_ONLY_REVIEW",
                classification="optional",
            )
        ]
        payload["joins"] = [
            {"id": "exploration", "requires": ["only"], "policy": "first-success"}
        ]
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("unsafe-first-success-nonredundant", issue_codes(result))

    def test_manual_gate_requires_exact_declared_gate_identity(self):
        payload = minimal_graph()
        payload["human_gates"] = ["human-approval"]
        payload["joins"] = [
            {
                "id": "human-approval",
                "requires": ["build"],
                "policy": "manual-gate",
            }
        ]
        self.assertTrue(validate_graph_contract(payload).valid)
        payload["joins"][0]["id"] = "different-gate"
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("manual-gate-mismatch", issue_codes(result))

    def test_all_required_and_required_plus_optional_preserve_required_nodes(self):
        payload = minimal_graph()
        payload["nodes"].append(node("optional", classification="optional"))
        payload["joins"][0]["requires"] = ["build", "optional"]
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("all-required-optional-node", issue_codes(result))

        payload["joins"][0]["policy"] = "required-plus-optional"
        self.assertTrue(validate_graph_contract(payload).valid)
        payload["joins"][0]["requires"] = ["optional"]
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("required-plus-optional-missing-required", issue_codes(result))

    def test_corrective_join_requires_provable_independent_responsibilities(self):
        payload = minimal_graph()
        payload["nodes"] = [
            node(
                "review",
                role="independent review",
                permission="READ_ONLY_REVIEW",
            ),
            node(
                "correct",
                role="corrective implementation",
                permission="CORRECTIVE_AUTHORIZED",
            ),
        ]
        payload["joins"] = [
            {
                "id": "finding-closure",
                "requires": ["review", "correct"],
                "policy": "corrective-join",
            }
        ]
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("corrective-join-responsibility-unproven", issue_codes(result))
        payload["nodes"][0]["role"] = "general worker"
        result = validate_graph_contract(payload)
        self.assertFalse(result.valid)
        self.assertIn("corrective-join-responsibility-unproven", issue_codes(result))
        payload["nodes"][0]["classification"] = "optional"
        result = validate_graph_contract(payload)
        self.assertIn("corrective-join-optional-node", issue_codes(result))


class NodeTransitionTests(unittest.TestCase):
    def test_complete_allowed_transition_table(self):
        expected = {
            "PENDING": {"READY", "HANDOFF", "BLOCKED", "CANCELLED"},
            "READY": {
                "RUNNING",
                "WAITING_RESOURCE",
                "HANDOFF",
                "BLOCKED",
                "CANCELLED",
            },
            "RUNNING": {
                "WAITING_RESOURCE",
                "SUCCEEDED",
                "NO_ACTION_REQUIRED",
                "DONE_WITH_CONCERNS",
                "FAILED",
                "NEEDS_CORRECTION",
                "HANDOFF",
                "BLOCKED",
                "CANCELLED",
            },
            "WAITING_RESOURCE": {
                "READY",
                "RUNNING",
                "HANDOFF",
                "BLOCKED",
                "CANCELLED",
            },
            "NEEDS_CORRECTION": {
                "READY",
                "HANDOFF",
                "BLOCKED",
                "CANCELLED",
            },
        }
        for previous in graph_contract.NODE_STATUSES:
            for next_status in graph_contract.NODE_STATUSES:
                with self.subTest(previous=previous, next_status=next_status):
                    self.assertEqual(
                        next_status in expected.get(previous, set()),
                        validate_node_transition(previous, next_status).allowed,
                    )

    def test_allowed_and_invalid_transitions_are_typed_and_deterministic(self):
        allowed = validate_node_transition("PENDING", "READY")
        denied = validate_node_transition("PENDING", "RUNNING")
        invalid = validate_node_transition("NOT_A_STATE", "READY")
        self.assertIsInstance(allowed, NodeTransitionResult)
        self.assertTrue(allowed.allowed)
        self.assertFalse(denied.allowed)
        self.assertEqual("transition-not-allowed", denied.reason)
        self.assertFalse(invalid.allowed)
        self.assertEqual("unknown-previous-status", invalid.reason)
        self.assertEqual(denied, validate_node_transition("PENDING", "RUNNING"))
        self.assertEqual(
            "unknown-previous-status",
            validate_node_transition([], "READY").reason,
        )

    def test_terminal_states_cannot_continue(self):
        terminal = {
            "SUCCEEDED",
            "NO_ACTION_REQUIRED",
            "DONE_WITH_CONCERNS",
            "FAILED",
            "HANDOFF",
            "BLOCKED",
            "CANCELLED",
        }
        for status in terminal:
            with self.subTest(status=status):
                result = validate_node_transition(status, "READY")
                self.assertFalse(result.allowed)
                self.assertEqual("terminal-status", result.reason)


class NodeResultValidationTests(unittest.TestCase):
    def test_valid_node_result_and_graph_binding(self):
        payload = minimal_result()
        result = validate_node_result(payload, minimal_graph())
        self.assertTrue(result.valid, result.to_json())
        self.assertEqual((), result.issues)
        self.assertIsNone(result.semantic_digest)

    def test_node_result_exact_fields_types_uniqueness_and_finding_bounds(self):
        payload = minimal_result()
        payload["unexpected"] = "value"
        payload["authority_change"] = 1
        payload["changed_paths"] = ["same", "same"]
        payload["findings"] = [
            {
                "finding_id": "finding",
                "severity": "P9",
                "summary": "x" * 4097,
                "evidence_refs": ["same", "same"],
                "unexpected": True,
            }
        ]
        result = validate_node_result(payload)
        self.assertFalse(result.valid)
        self.assertTrue(
            {
                "unknown-field",
                "invalid-type",
                "duplicate-item",
                "invalid-enum",
                "string-too-long",
            }.issubset(issue_codes(result)),
            result.to_json(),
        )

    def test_no_action_required_requires_scope_decision_and_evidence(self):
        payload = minimal_result("NO_ACTION_REQUIRED")
        payload["changed_paths"] = []
        payload["evidence_refs"] = []
        result = validate_node_result(payload)
        self.assertFalse(result.valid)
        self.assertTrue(
            {
                "no-action-missing-inspected-scope",
                "no-action-missing-decision",
                "no-action-missing-evidence",
            }.issubset(issue_codes(result)),
            result.to_json(),
        )
        payload["inspected_scope"] = ["sagekit/graph_contract.py"]
        payload["decision"] = "No change was required after focused inspection."
        payload["evidence_refs"] = ["review:focused"]
        self.assertTrue(validate_node_result(payload).valid)

    def test_done_with_concerns_remains_distinct_and_does_not_auto_succeed(self):
        payload = minimal_result("DONE_WITH_CONCERNS")
        result = validate_node_result(payload, minimal_graph())
        self.assertTrue(result.valid, result.to_json())
        self.assertNotEqual("SUCCEEDED", payload["status"])
        self.assertFalse(
            validate_node_transition("DONE_WITH_CONCERNS", "SUCCEEDED").allowed
        )
        self.assertFalse(
            validate_node_transition("NO_ACTION_REQUIRED", "SUCCEEDED").allowed
        )

    def test_authority_change_requires_bounded_decision(self):
        payload = minimal_result()
        payload["authority_change"] = True
        result = validate_node_result(payload)
        self.assertFalse(result.valid)
        self.assertIn("authority-change-missing-decision", issue_codes(result))
        payload["decision"] = "Request a higher-authority decision."
        self.assertTrue(validate_node_result(payload).valid)

    def test_unknown_node_and_unknown_next_node_are_rejected_when_graph_is_present(self):
        payload = minimal_result()
        payload["node_id"] = "unknown"
        payload["proposed_next_nodes"] = ["also-unknown"]
        result = validate_node_result(payload, minimal_graph())
        self.assertFalse(result.valid)
        self.assertTrue(
            {"unknown-node", "unknown-proposed-next-node"}.issubset(
                issue_codes(result)
            ),
            result.to_json(),
        )

    def test_node_result_cannot_carry_permission_gate_or_authority_mutations(self):
        payload = minimal_result()
        payload["permission"] = "SUBMIT_AUTHORIZED"
        payload["human_gates"] = []
        payload["source_authority"] = {"identity": "replacement"}
        result = validate_node_result(payload, minimal_graph())
        self.assertFalse(result.valid)
        unknown_paths = {
            issue.path for issue in result.issues if issue.code == "unknown-field"
        }
        self.assertEqual(
            {"$.permission", "$.human_gates", "$.source_authority"},
            unknown_paths,
        )

    def test_read_only_graph_node_cannot_report_changed_paths(self):
        graph = minimal_graph()
        graph["nodes"][0]["permission"] = "READ_ONLY_REVIEW"
        payload = minimal_result()
        result = validate_node_result(payload, graph)
        self.assertFalse(result.valid)
        self.assertIn("read-only-node-changed-paths", issue_codes(result))
        payload["changed_paths"] = []
        self.assertTrue(validate_node_result(payload, graph).valid)


class DeterminismAndPurityTests(unittest.TestCase):
    def test_inputs_are_not_mutated(self):
        graph = minimal_graph()
        result_payload = minimal_result()
        graph_before = copy.deepcopy(graph)
        result_before = copy.deepcopy(result_payload)
        validate_graph_contract(graph)
        canonical_graph_digest(graph)
        validate_node_result(result_payload, graph)
        self.assertEqual(graph_before, graph)
        self.assertEqual(result_before, result_payload)

    def test_issue_order_and_json_representation_are_stable_and_bounded(self):
        payload = minimal_graph()
        for index in range(graph_contract.MAX_VALIDATION_ISSUES + 25):
            payload[f"unknown-{index:03d}"] = index
        first = validate_graph_contract(payload)
        second = validate_graph_contract(copy.deepcopy(payload))
        self.assertFalse(first.valid)
        self.assertEqual(first, second)
        self.assertEqual(first.to_json(), second.to_json())
        self.assertLessEqual(len(first.issues), graph_contract.MAX_VALIDATION_ISSUES)
        self.assertIn("too-many-issues", issue_codes(first))
        keys = [(issue.path, issue.code, issue.message) for issue in first.issues]
        self.assertEqual(sorted(keys), keys)
        self.assertTrue(all(isinstance(issue, GraphValidationIssue) for issue in first.issues))

    def test_dependency_issue_paths_identify_each_array_item(self):
        payload = minimal_graph()
        payload["nodes"][0]["depends_on"] = ["missing-a", "missing-b"]
        result = validate_graph_contract(payload)
        missing_paths = [
            issue.path
            for issue in result.issues
            if issue.code == "missing-dependency"
        ]
        self.assertEqual(
            ["$.nodes[0].depends_on[0]", "$.nodes[0].depends_on[1]"],
            missing_paths,
        )

    def test_schema_enums_and_validator_constants_stay_in_sync(self):
        graph_schema = json.loads(GRAPH_SCHEMA.read_text(encoding="utf-8"))
        result_schema = json.loads(NODE_RESULT_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            frozenset(graph_schema["properties"]),
            graph_contract._GRAPH_FIELDS,
        )
        self.assertEqual(
            frozenset(graph_schema["required"]),
            graph_contract._GRAPH_REQUIRED_FIELDS,
        )
        self.assertEqual(
            frozenset(graph_schema["$defs"]["node"]["properties"]),
            graph_contract._NODE_FIELDS,
        )
        self.assertEqual(
            frozenset(graph_schema["$defs"]["join"]["properties"]),
            graph_contract._JOIN_FIELDS,
        )
        self.assertEqual(
            frozenset(result_schema["properties"]),
            graph_contract._NODE_RESULT_FIELDS,
        )
        self.assertEqual(
            frozenset(result_schema["required"]),
            graph_contract._NODE_RESULT_REQUIRED_FIELDS,
        )
        self.assertEqual(
            frozenset(result_schema["$defs"]["finding"]["properties"]),
            graph_contract._FINDING_FIELDS,
        )
        self.assertEqual(
            frozenset(graph_schema["properties"]["governance_level"]["enum"]),
            graph_contract.GOVERNANCE_LEVELS,
        )
        self.assertEqual(
            frozenset(graph_schema["properties"]["autonomy_level"]["enum"]),
            graph_contract.AUTONOMY_LEVELS,
        )
        self.assertEqual(
            frozenset(
                graph_schema["$defs"]["node"]["properties"]["permission"]["enum"]
            ),
            graph_contract.PERMISSION_MODES,
        )
        self.assertEqual(
            frozenset(
                graph_schema["$defs"]["join"]["properties"]["policy"]["enum"]
            ),
            graph_contract.JOIN_POLICIES,
        )
        self.assertEqual(
            frozenset(result_schema["properties"]["status"]["enum"]),
            graph_contract.NODE_STATUSES,
        )
        self.assertEqual(
            frozenset(
                result_schema["$defs"]["finding"]["properties"]["severity"]["enum"]
            ),
            graph_contract.FINDING_SEVERITIES,
        )

    def test_internal_api_is_importable_only_from_graph_contract_module(self):
        self.assertIs(validate_graph_contract, graph_contract.validate_graph_contract)
        self.assertIs(validate_node_result, graph_contract.validate_node_result)
        self.assertIs(validate_node_transition, graph_contract.validate_node_transition)
        self.assertIs(canonical_graph_digest, graph_contract.canonical_graph_digest)
        import sagekit

        for name in (
            "validate_graph_contract",
            "validate_node_result",
            "validate_node_transition",
            "canonical_graph_digest",
        ):
            self.assertNotIn(name, vars(sagekit))


if __name__ == "__main__":
    unittest.main()
