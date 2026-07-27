import copy
import hashlib
import json
import unittest

from sagekit.evidence import (
    EvidenceLineageOutcome,
    canonical_node_input_fingerprint,
    resolve_evidence_lineage,
)
from sagekit.graph_contract import canonical_graph_digest
from sagekit.graph_evolution_contract import (
    canonical_graph_evolution_digest,
    validate_graph_evolution_error,
    validate_graph_evolution_proposal,
)
from sagekit.graph_evolution_proposal import (
    GraphEvolutionProposalOutcome,
    build_graph_evolution_proposal,
)


OPERATIONS = (
    "ADD_CORRECTIVE",
    "ADD_VERIFICATION",
    "ADD_INVESTIGATION",
    "SPLIT_PENDING",
    "DISABLE_OPTIONAL_PENDING",
    "NO_CHANGE",
)
JOIN_DEFINITION_FINGERPRINT_DOMAIN = (
    b"sagekit-evidence-lineage-join-definition-v1\0"
)


def parent_graph():
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph/spec",
        "generation": 7,
        "source_authority": {
            "identity": "pm/rebuild",
            "reference": "authority/stage6",
        },
        "governance_level": "Heavy",
        "autonomy_level": "turn-based",
        "completion_verifier": "verifier/completion",
        "human_gates": ["gate/acceptance"],
        "nodes": [
            {
                "id": "node/controller",
                "role": "Controller",
                "depends_on": [],
                "permission": "WRITE_AUTHORIZED",
                "verifier": "verifier/controller",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": [],
                "classification": "required",
            },
            {
                "id": "node/verify",
                "role": "Verifier",
                "depends_on": [],
                "permission": "READ_ONLY_REVIEW",
                "verifier": "verifier/focused",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": [],
                "classification": "required",
            },
            {
                "id": "node/split",
                "role": "Implementer",
                "depends_on": [],
                "permission": "WRITE_AUTHORIZED",
                "verifier": "verifier/split",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": ["scope/original"],
                "classification": "required",
            },
            {
                "id": "node/optional",
                "role": "Investigator",
                "depends_on": [],
                "permission": "READ_ONLY_REVIEW",
                "verifier": "verifier/investigation",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": [],
                "classification": "optional",
            },
        ],
        "joins": [
            {
                "id": "gate/acceptance",
                "requires": ["node/controller", "node/verify"],
                "policy": "manual-gate",
            }
        ],
    }


def authority():
    return {
        "authority_id": "pm/rebuild",
        "authority_role": "PROJECT_MANAGER",
        "authority_ref": "authority/stage6",
    }


def request(operation):
    graph = parent_graph()
    subjects = {
        "ADD_CORRECTIVE": "node/corrective",
        "ADD_VERIFICATION": "node/new-verify",
        "ADD_INVESTIGATION": "node/investigate",
        "SPLIT_PENDING": "node/split",
        "DISABLE_OPTIONAL_PENDING": "node/optional",
        "NO_CHANGE": "node/verify",
    }
    reasons = {
        "ADD_CORRECTIVE": "OBSERVED_FAILURE",
        "ADD_VERIFICATION": "VERIFICATION_GAP",
        "ADD_INVESTIGATION": "BLOCKING_UNCERTAINTY",
        "SPLIT_PENDING": "NODE_TOO_BROAD",
        "DISABLE_OPTIONAL_PENDING": "OPTIONAL_NODE_NO_LONGER_DECISIVE",
        "NO_CHANGE": "EXISTING_GRAPH_SUFFICIENT",
    }
    value = {
        "schema_id": "urn:sagekit:graph-evolution:v1:request",
        "schema_version": 1,
        "request_id": f"request/{operation.lower()}",
        "operation": operation,
        "graph_id": graph["graph_id"],
        "parent_generation": graph["generation"],
        "parent_graph_digest": canonical_graph_digest(graph),
        "authority": authority(),
        "proposer": {
            "node_id": "node/controller",
            "role": "Controller",
            "permission": "WRITE_AUTHORIZED",
        },
        "node_id": subjects[operation],
        "change_class": "C1",
        "reason_code": reasons[operation],
        "evidence_refs": ["evidence/stage5/failure-001"],
        "decision_refs": ["decision/review-001"],
        "affected_paths": ["sagekit/graph_contract.py"],
        "stage5_lineage_digest": stage5_lineage(graph).binding_digest,
    }
    if operation == "ADD_CORRECTIVE":
        value["finding_ref"] = "finding/review-001"
        value["root_cause_ref"] = "root-cause/review-001"
    if operation in {"SPLIT_PENDING", "DISABLE_OPTIONAL_PENDING"}:
        value["subject_status"] = "PENDING"
    return value


def preauthorization():
    graph = parent_graph()
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:preauthorization",
        "schema_version": 1,
        "preauthorization_id": "preauth/stage6-001",
        "graph_id": graph["graph_id"],
        "parent_generation": graph["generation"],
        "parent_graph_digest": canonical_graph_digest(graph),
        "authority": authority(),
        "allowed_operations": list(OPERATIONS),
        "allowed_change_classes": ["C0", "C1"],
        "allowed_node_ids": [
            "node/controller",
            "node/verify",
            "node/split",
            "node/optional",
            "node/corrective",
            "node/new-verify",
            "node/investigate",
            "node/split-part",
        ],
        "allowed_roles": [
            "Controller",
            "Verifier",
            "Corrector",
            "Investigator",
            "Implementer",
        ],
        "allowed_permissions": [
            "READ_ONLY_REVIEW",
            "WRITE_AUTHORIZED",
            "CORRECTIVE_AUTHORIZED",
        ],
        "allowed_paths": ["sagekit/**", "tests/unit/**"],
        "generation_budget": {
            "max_target_generation": 10,
            "remaining_generations": 3,
        },
        "operation_budgets": {
            "ADD_CORRECTIVE": 2,
            "ADD_VERIFICATION": 2,
            "ADD_INVESTIGATION": 1,
            "SPLIT_PENDING": 1,
            "DISABLE_OPTIONAL_PENDING": 1,
            "NO_CHANGE": 3,
        },
        "evaluator": {
            "node_id": "node/verify",
            "role": "Verifier",
            "permission": "READ_ONLY_REVIEW",
            "authority_ref": "authority/evaluator",
            "independent": True,
        },
        "stop_conditions": [
            "BUDGET_EXHAUSTED",
            "NO_PROGRESS",
            "EVALUATOR_REJECTED",
            "AUTHORITY_CHANGED",
            "CONTRACT_CHANGED",
            "PERMISSION_EXPANSION",
            "GATE_OR_VERIFIER_REMOVAL",
        ],
    }


def stage5_lineage(graph=None):
    graph = parent_graph() if graph is None else graph
    graph_digest = canonical_graph_digest(graph)
    output_digests = {
        node["id"]: format(index, "064x")
        for index, node in enumerate(graph["nodes"], start=1)
    }
    lineage_nodes = [
        {
            "lineage_node_id": node["id"],
            "owner_kind": "GRAPH_NODE",
            "owner_id": node["id"],
            "input_fingerprint": "0" * 64,
            "output_fingerprint": output_digests[node["id"]],
        }
        for node in graph["nodes"]
    ]
    lineage_nodes.extend(
        [
            {
                "lineage_node_id": "gate/acceptance",
                "owner_kind": "JOIN",
                "owner_id": "gate/acceptance",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": "a" * 64,
            },
            {
                "lineage_node_id": "candidate/release",
                "owner_kind": "CANDIDATE",
                "owner_id": "candidate/release",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": "b" * 64,
            },
            {
                "lineage_node_id": "evidence/final",
                "owner_kind": "EVIDENCE",
                "owner_id": "evidence/final",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": "c" * 64,
            },
        ]
    )
    lineage_edges = [
        {
            "source_node_id": source,
            "target_node_id": "gate/acceptance",
            "edge_type": "NODE_OUTPUT",
            "source_output_fingerprint": "0" * 64,
            "target_input_fingerprint": "0" * 64,
        }
        for source in ("node/controller", "node/verify")
    ]
    lineage_edges.extend(
        [
            {
                "source_node_id": "gate/acceptance",
                "target_node_id": "evidence/final",
                "edge_type": "JOIN_INTEGRATION",
                "source_output_fingerprint": "0" * 64,
                "target_input_fingerprint": "0" * 64,
            },
            {
                "source_node_id": "candidate/release",
                "target_node_id": "evidence/final",
                "edge_type": "CANDIDATE",
                "source_output_fingerprint": "0" * 64,
                "target_input_fingerprint": "0" * 64,
            },
        ]
    )
    graph_join = graph["joins"][0]
    join_projection = {
        "join_definition": {
            "id": graph_join["id"],
            "policy": graph_join["policy"],
            "requires": sorted(graph_join["requires"]),
        },
        "optional_member_node_ids": [],
    }
    join_definition_fingerprint = hashlib.sha256(
        JOIN_DEFINITION_FINGERPRINT_DOMAIN
        + json.dumps(
            join_projection,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    snapshot = {
        "graph_binding": {
            "graph_id": graph["graph_id"],
            "graph_generation": graph["generation"],
            "graph_digest": graph_digest,
        },
        "stage4_bindings": {
            "ready_input_digest": "d" * 64,
            "transition_bindings": [
                {
                    "node_id": node["id"],
                    "transition_input_digest": "e" * 64,
                    "node_result_digest": output_digests[node["id"]],
                }
                for node in graph["nodes"]
            ],
        },
        "lineage_nodes": lineage_nodes,
        "lineage_edges": lineage_edges,
        "join_integrations": [
            {
                "join_id": graph_join["id"],
                "policy": graph_join["policy"],
                "definition_fingerprint": join_definition_fingerprint,
                "contributor_node_ids": list(graph_join["requires"]),
                "ready_input_digest": "d" * 64,
                "external_decision_refs": ["decision/manual-gate"],
            }
        ],
        "final_evidence_node_id": "evidence/final",
    }
    nodes_by_id = {node["lineage_node_id"]: node for node in lineage_nodes}
    incoming = {node_id: [] for node_id in nodes_by_id}
    for edge in lineage_edges:
        source = nodes_by_id[edge["source_node_id"]]
        edge["source_output_fingerprint"] = source["output_fingerprint"]
        incoming[edge["target_node_id"]].append(
            {
                "edge_type": edge["edge_type"],
                "source_node_id": edge["source_node_id"],
                "source_output_fingerprint": source["output_fingerprint"],
            }
        )
    for node_id, node in nodes_by_id.items():
        node["input_fingerprint"] = canonical_node_input_fingerprint(
            snapshot["graph_binding"],
            incoming[node_id],
        )
    for edge in lineage_edges:
        edge["target_input_fingerprint"] = nodes_by_id[edge["target_node_id"]][
            "input_fingerprint"
        ]
    lineage_input = {
        "schema_id": "urn:sagekit:evidence-lineage:v1:input",
        "schema_version": 1,
        "baseline": snapshot,
        "candidate": copy.deepcopy(snapshot),
    }
    outcome = resolve_evidence_lineage(graph, lineage_input)
    if not outcome.succeeded:
        raise AssertionError(f"synthetic Stage 5 lineage failed: {outcome.error}")
    return outcome


def build(operation, *, graph=None, req=None, preauth=None, lineage=None):
    graph = parent_graph() if graph is None else graph
    req = request(operation) if req is None else req
    preauth = preauthorization() if preauth is None else preauth
    lineage = stage5_lineage(graph) if lineage is None else lineage
    return build_graph_evolution_proposal(graph, req, preauth, lineage)


class GraphEvolutionProposalTests(unittest.TestCase):
    def test_all_six_operations_build_valid_digest_bound_proposals(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                req = request(operation)
                preauth = preauthorization()
                outcome = build(operation, req=req, preauth=preauth)
                self.assertTrue(outcome.succeeded, outcome.error)
                self.assertIsNone(outcome.error)
                result = outcome.result
                proposal = result["proposal"]
                validation = validate_graph_evolution_proposal(proposal)
                self.assertTrue(validation.valid, validation.issues)
                self.assertEqual(
                    canonical_graph_evolution_digest("request", req),
                    proposal["request_digest"],
                )
                self.assertEqual(
                    canonical_graph_evolution_digest(
                        "preauthorization",
                        preauth,
                    ),
                    proposal["preauthorization_digest"],
                )
                self.assertEqual(validation.digest, result["proposal_digest"])
                for field in (
                    "grants_execution_authority",
                    "grants_graph_mutation_authority",
                    "grants_gate_authority",
                    "grants_write_authority",
                    "grants_acceptance_authority",
                ):
                    self.assertIs(result[field], False)

                if operation == "NO_CHANGE":
                    self.assertNotIn("target_generation", proposal)
                    self.assertNotIn("target_graph", proposal)
                    self.assertNotIn("target_graph_digest", proposal)
                else:
                    self.assertEqual(8, proposal["target_generation"])
                    self.assertEqual(
                        8,
                        proposal["target_graph"]["generation"],
                    )
                    self.assertEqual(
                        canonical_graph_digest(proposal["target_graph"]),
                        proposal["target_graph_digest"],
                    )

    def test_operation_specific_deltas_are_minimal_and_preserve_controls(self):
        graph = parent_graph()
        parent_nodes = {node["id"]: node for node in graph["nodes"]}

        corrective = build("ADD_CORRECTIVE").proposal["target_graph"]
        corrective_node = corrective["nodes"][-1]
        self.assertEqual("CORRECTIVE_AUTHORIZED", corrective_node["permission"])
        self.assertEqual("required", corrective_node["classification"])

        verification = build("ADD_VERIFICATION").proposal["target_graph"]
        verification_node = verification["nodes"][-1]
        self.assertEqual("READ_ONLY_REVIEW", verification_node["permission"])
        self.assertEqual("required", verification_node["classification"])

        investigation = build("ADD_INVESTIGATION").proposal["target_graph"]
        investigation_node = investigation["nodes"][-1]
        self.assertEqual("READ_ONLY_REVIEW", investigation_node["permission"])
        self.assertEqual("optional", investigation_node["classification"])
        self.assertFalse(
            any(
                investigation_node["id"] in join["requires"]
                for join in investigation["joins"]
            )
        )

        split = build("SPLIT_PENDING").proposal["target_graph"]
        split_nodes = {node["id"]: node for node in split["nodes"]}
        self.assertEqual(parent_nodes["node/split"], split_nodes["node/split"])
        split_part = split_nodes["node/split-part"]
        for field in ("role", "permission", "verifier", "classification"):
            self.assertEqual(parent_nodes["node/split"][field], split_part[field])

        disabled = build("DISABLE_OPTIONAL_PENDING").proposal["target_graph"]
        self.assertNotIn(
            "node/optional",
            {node["id"] for node in disabled["nodes"]},
        )

        for target in (
            corrective,
            verification,
            investigation,
            split,
            disabled,
        ):
            for field in (
                "source_authority",
                "governance_level",
                "autonomy_level",
                "completion_verifier",
                "human_gates",
            ):
                self.assertEqual(graph[field], target[field])
            target_nodes = {node["id"]: node for node in target["nodes"]}
            for node_id in set(parent_nodes) & set(target_nodes):
                self.assertEqual(parent_nodes[node_id], target_nodes[node_id])

    def test_inputs_and_outcome_snapshots_are_immutable_and_deterministic(self):
        graph = parent_graph()
        req = request("ADD_VERIFICATION")
        preauth = preauthorization()
        lineage = stage5_lineage(graph)
        originals = copy.deepcopy((graph, req, preauth))

        first = build_graph_evolution_proposal(graph, req, preauth, lineage)
        second = build_graph_evolution_proposal(graph, req, preauth, lineage)

        self.assertEqual(first, second)
        self.assertEqual(originals, (graph, req, preauth))
        self.assertRaises(
            AttributeError,
            setattr,
            first,
            "_result_snapshot",
            None,
        )
        exposed = first.result
        exposed["proposal"]["target_graph"]["nodes"].clear()
        self.assertTrue(first.result["proposal"]["target_graph"]["nodes"])

    def test_invalid_lineage_binding_and_preauthorization_fail_closed(self):
        wrong_graph = parent_graph()
        wrong_graph["generation"] = 6
        lineage_error = build(
            "ADD_VERIFICATION",
            lineage=stage5_lineage(wrong_graph),
        )
        self.assertFalse(lineage_error.succeeded)
        self.assertIsNone(lineage_error.proposal)
        self.assertTrue(validate_graph_evolution_error(lineage_error.error).valid)
        self.assertEqual(
            "LINEAGE_GRAPH_BINDING_MISMATCH",
            lineage_error.error["issues"][0]["issue_code"],
        )

        denied = preauthorization()
        denied["allowed_operations"].remove("ADD_VERIFICATION")
        denied["operation_budgets"]["ADD_VERIFICATION"] = 0
        preauth_error = build("ADD_VERIFICATION", preauth=denied)
        self.assertFalse(preauth_error.succeeded)
        self.assertIsNone(preauth_error.proposal)
        self.assertTrue(validate_graph_evolution_error(preauth_error.error).valid)
        self.assertIn(
            "OPERATION_NOT_PREAUTHORIZED",
            {issue["issue_code"] for issue in preauth_error.error["issues"]},
        )

    def test_request_must_reuse_owner_produced_stage5_binding_digest(self):
        graph = parent_graph()
        lineage = stage5_lineage(graph)
        req = request("ADD_VERIFICATION")
        self.assertEqual(lineage.binding_digest, req["stage5_lineage_digest"])

        built = build(
            "ADD_VERIFICATION",
            graph=graph,
            req=req,
            lineage=lineage,
        )
        self.assertTrue(built.succeeded, built.error)
        self.assertEqual(
            lineage.binding_digest,
            built.proposal["stage5_lineage_digest"],
        )
        self.assertTrue(validate_graph_evolution_proposal(built.proposal).valid)

        for replacement in ("b" * 64, "c" * 64):
            with self.subTest(replacement=replacement[0]):
                substituted = copy.deepcopy(req)
                substituted["stage5_lineage_digest"] = replacement
                rejected = build(
                    "ADD_VERIFICATION",
                    graph=graph,
                    req=substituted,
                    lineage=lineage,
                )
                self.assertFalse(rejected.succeeded)
                self.assertIn(
                    "LINEAGE_DIGEST_MISMATCH",
                    {
                        issue["issue_code"]
                        for issue in rejected.error["issues"]
                    },
                )

        unbound = EvidenceLineageOutcome._from_result(lineage.result)
        rejected = build(
            "ADD_VERIFICATION",
            graph=graph,
            req=req,
            lineage=unbound,
        )
        self.assertFalse(rejected.succeeded)
        self.assertEqual(
            "VALIDATED_LINEAGE_OUTCOME_REQUIRED",
            rejected.error["issues"][0]["issue_code"],
        )

    def test_invalid_or_oversized_inputs_return_bounded_typed_errors(self):
        cyclic = request("ADD_VERIFICATION")
        cyclic["authority"] = cyclic
        invalid = build("ADD_VERIFICATION", req=cyclic)
        self.assertIsInstance(invalid, GraphEvolutionProposalOutcome)
        self.assertFalse(invalid.succeeded)
        self.assertLessEqual(len(invalid.error["issues"]), 100)
        self.assertTrue(validate_graph_evolution_error(invalid.error).valid)

        oversized = request("ADD_VERIFICATION")
        oversized["request_id"] = "x" * (1024 * 1024 + 1)
        too_large = build("ADD_VERIFICATION", req=oversized)
        self.assertFalse(too_large.succeeded)
        self.assertEqual("INPUT_TOO_LARGE", too_large.error["error_code"])
        self.assertLessEqual(len(too_large.error["issues"]), 100)
        self.assertTrue(validate_graph_evolution_error(too_large.error).valid)

    def test_outcome_cannot_be_caller_constructed(self):
        with self.assertRaises(ValueError):
            GraphEvolutionProposalOutcome()


if __name__ == "__main__":
    unittest.main()
