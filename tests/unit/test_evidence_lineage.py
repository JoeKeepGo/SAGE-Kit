from __future__ import annotations

import copy
import unittest

from sagekit.candidate import CandidateFingerprint
from sagekit.change_control import ChangeClass
from sagekit.evidence import (
    ChangeEvent,
    EvidenceFingerprint,
    assess_evidence,
    canonical_join_integration_fingerprint,
    canonical_node_input_fingerprint,
    canonical_node_output_fingerprint,
    resolve_evidence_lineage,
)
from sagekit.graph_contract import canonical_graph_digest
from sagekit.ready_resolver import canonical_ready_input_digest
from sagekit.transition_resolver import canonical_node_result_digest


SHA = {
    name: format(index, "064x")
    for index, name in enumerate(
        (
            "ready",
            "path-old",
            "path-new",
            "contract-old",
            "contract-new",
            "authority-old",
            "authority-new",
            "root",
            "successor",
            "sibling",
            "join",
            "candidate-old",
            "candidate-new",
            "evidence",
            "transition-root",
            "transition-successor",
            "transition-sibling",
        ),
        start=1,
    )
}


def graph_node(
    node_id: str,
    *,
    depends_on: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "role": "evidence-lineage-test",
        "depends_on": [] if depends_on is None else depends_on,
        "permission": "READ_ONLY_REVIEW",
        "verifier": "evidence-lineage-test",
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": [],
        "classification": "required",
    }


def graph() -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph/evidence-lineage",
        "generation": 7,
        "source_authority": {
            "identity": "Stage 5B test authority",
            "reference": "evidence-lineage/stage-5b",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [
            graph_node("node/root"),
            graph_node("node/successor", depends_on=["node/root"]),
            graph_node("node/sibling"),
        ],
        "joins": [
            {
                "id": "join/review",
                "requires": ["node/root", "node/successor"],
                "policy": "all-required",
            }
        ],
    }


def node_result(node_id: str) -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:node-result",
        "schema_version": 1,
        "node_id": node_id,
        "status": "SUCCEEDED",
        "changed_paths": [],
        "evidence_refs": [],
        "findings": [],
        "authority_change": False,
        "proposed_next_nodes": [],
    }


def ready_input(candidate_graph: dict[str, object]) -> dict[str, object]:
    return {
        "schema_id": "urn:sagekit:ready-resolution:v1:input",
        "schema_version": 1,
        "graph_digest": canonical_graph_digest(candidate_graph),
        "graph_generation": candidate_graph["generation"],
        "node_states": [
            {
                "node_id": item["id"],
                "status": "SUCCEEDED",
                "result_digest": SHA[
                    str(item["id"]).removeprefix("node/")
                ],
                "evidence_refs": [],
            }
            for item in candidate_graph["nodes"]
        ],
        "resource_availability": [],
        "external_join_decisions": [],
    }


def _node(
    node_id: str,
    owner_kind: str,
    owner_id: str,
    output_fingerprint: str,
) -> dict[str, object]:
    return {
        "lineage_node_id": node_id,
        "owner_kind": owner_kind,
        "owner_id": owner_id,
        "input_fingerprint": "0" * 64,
        "output_fingerprint": output_fingerprint,
    }


def _edge(
    source: str,
    target: str,
    edge_type: str,
) -> dict[str, object]:
    return {
        "source_node_id": source,
        "target_node_id": target,
        "edge_type": edge_type,
        "source_output_fingerprint": "0" * 64,
        "target_input_fingerprint": "0" * 64,
    }


def _refresh_fingerprints(snapshot: dict[str, object]) -> None:
    nodes = {
        item["lineage_node_id"]: item for item in snapshot["lineage_nodes"]
    }
    incoming: dict[str, list[dict[str, str]]] = {
        node_id: [] for node_id in nodes
    }
    for edge in snapshot["lineage_edges"]:
        source = nodes[edge["source_node_id"]]
        edge["source_output_fingerprint"] = source["output_fingerprint"]
        incoming[edge["target_node_id"]].append(
            {
                "edge_type": edge["edge_type"],
                "source_node_id": edge["source_node_id"],
                "source_output_fingerprint": source["output_fingerprint"],
            }
        )
    for node_id, node in nodes.items():
        node["input_fingerprint"] = canonical_node_input_fingerprint(
            snapshot["graph_binding"],
            incoming[node_id],
        )
    for edge in snapshot["lineage_edges"]:
        edge["target_input_fingerprint"] = nodes[edge["target_node_id"]][
            "input_fingerprint"
        ]


def snapshot(candidate_graph: dict[str, object]) -> dict[str, object]:
    digest = canonical_graph_digest(candidate_graph)
    value: dict[str, object] = {
        "graph_binding": {
            "graph_id": candidate_graph["graph_id"],
            "graph_generation": candidate_graph["generation"],
            "graph_digest": digest,
        },
        "stage4_bindings": {
            "ready_input_digest": SHA["ready"],
            "transition_bindings": [
                {
                    "node_id": "node/root",
                    "transition_input_digest": SHA["transition-root"],
                    "node_result_digest": SHA["root"],
                },
                {
                    "node_id": "node/successor",
                    "transition_input_digest": SHA["transition-successor"],
                    "node_result_digest": SHA["successor"],
                },
                {
                    "node_id": "node/sibling",
                    "transition_input_digest": SHA["transition-sibling"],
                    "node_result_digest": SHA["sibling"],
                },
            ],
        },
        "lineage_nodes": [
            _node("path/src", "PATH", "src/feature.py", SHA["path-old"]),
            _node(
                "contract/core",
                "CONTRACT",
                "contract/core",
                SHA["contract-old"],
            ),
            _node(
                "authority/review",
                "AUTHORITY",
                "authority/review",
                SHA["authority-old"],
            ),
            _node("node/root", "GRAPH_NODE", "node/root", SHA["root"]),
            _node(
                "node/successor",
                "GRAPH_NODE",
                "node/successor",
                SHA["successor"],
            ),
            _node("node/sibling", "GRAPH_NODE", "node/sibling", SHA["sibling"]),
            _node("join/review", "JOIN", "join/review", SHA["join"]),
            _node(
                "candidate/release",
                "CANDIDATE",
                "candidate/release",
                SHA["candidate-old"],
            ),
            _node(
                "evidence/final",
                "EVIDENCE",
                "evidence/final",
                SHA["evidence"],
            ),
        ],
        "lineage_edges": [
            _edge("path/src", "node/root", "PATH"),
            _edge("contract/core", "node/root", "CONTRACT"),
            _edge("authority/review", "node/root", "AUTHORITY"),
            _edge("node/root", "join/review", "NODE_OUTPUT"),
            _edge("node/successor", "join/review", "NODE_OUTPUT"),
            _edge("join/review", "evidence/final", "JOIN_INTEGRATION"),
            _edge("candidate/release", "evidence/final", "CANDIDATE"),
        ],
        "join_integrations": [
            {
                "join_id": "join/review",
                "policy": "all-required",
                "definition_fingerprint": SHA["join"],
                "contributor_node_ids": ["node/root", "node/successor"],
                "ready_input_digest": SHA["ready"],
                "external_decision_refs": [],
            }
        ],
        "final_evidence_node_id": "evidence/final",
    }
    _refresh_fingerprints(value)
    return value


def lineage_input(
    candidate_graph: dict[str, object],
) -> dict[str, object]:
    baseline = snapshot(candidate_graph)
    return {
        "schema_id": "urn:sagekit:evidence-lineage:v1:input",
        "schema_version": 1,
        "baseline": baseline,
        "candidate": copy.deepcopy(baseline),
    }


def decision(outcome, node_id: str) -> dict[str, object]:
    assert outcome.result is not None
    return outcome.result["decisions"][node_id]


class EvidenceLineageFingerprintTests(unittest.TestCase):
    def test_node_input_fixed_vector_and_owner_output_delegation(self) -> None:
        fingerprint = canonical_node_input_fingerprint(
            {
                "graph_id": "graph/跨语言",
                "graph_generation": 7,
                "graph_digest": "0" * 64,
            },
            [
                {
                    "edge_type": "TOOLCHAIN",
                    "source_node_id": "tool/编译",
                    "source_output_fingerprint": "2" * 64,
                },
                {
                    "edge_type": "PATH",
                    "source_node_id": "path/src",
                    "source_output_fingerprint": "1" * 64,
                },
            ],
        )
        self.assertEqual(
            "150bae360e3f85fb95f4eb5b5f3b82d772eebaabd17a2daa93d57f5b20121b72",
            fingerprint,
        )

        candidate_graph = graph()
        result = node_result("node/root")
        self.assertEqual(
            canonical_node_result_digest(candidate_graph, result),
            canonical_node_output_fingerprint(candidate_graph, result),
        )
        candidate = CandidateFingerprint(
            "head",
            "diff",
            "contract",
            "dependency",
            True,
            True,
        )
        self.assertEqual(
            candidate.digest,
            canonical_node_output_fingerprint(candidate),
        )

    def test_join_fingerprint_consumes_graph_ready_decision_and_external_refs(
        self,
    ) -> None:
        candidate_graph = {
            **graph(),
            "human_gates": ["join/review"],
            "nodes": [graph_node("node/root")],
            "joins": [
                {
                    "id": "join/review",
                    "requires": ["node/root"],
                    "policy": "manual-gate",
                }
            ],
        }
        original = ready_input(candidate_graph)
        original["external_join_decisions"] = [
            {
                "join_id": "join/review",
                "decision": "SATISFIED",
                "authority_ref": "authority/reviewer",
                "evidence_refs": ["evidence/review"],
            }
        ]
        baseline = canonical_join_integration_fingerprint(
            candidate_graph,
            original,
            "join/review",
        )
        self.assertIsNotNone(baseline)

        definition_changed = copy.deepcopy(candidate_graph)
        definition_changed["joins"][0]["policy"] = "corrective-join"
        definition_changed["human_gates"] = []
        changed_ready = copy.deepcopy(original)
        changed_ready["graph_digest"] = canonical_graph_digest(definition_changed)
        self.assertNotEqual(
            baseline,
            canonical_join_integration_fingerprint(
                definition_changed,
                changed_ready,
                "join/review",
            ),
        )

        external_changed = copy.deepcopy(original)
        external_changed["external_join_decisions"][0][
            "evidence_refs"
        ] = ["evidence/replacement"]
        self.assertNotEqual(
            baseline,
            canonical_join_integration_fingerprint(
                candidate_graph,
                external_changed,
                "join/review",
            ),
        )


class EvidenceLineageResolutionTests(unittest.TestCase):
    def test_narrow_path_targets_overlap_successor_and_join_not_sibling(
        self,
    ) -> None:
        candidate_graph = graph()
        payload = lineage_input(candidate_graph)
        candidate = payload["candidate"]
        nodes = {
            item["lineage_node_id"]: item
            for item in candidate["lineage_nodes"]
        }
        nodes["path/src"]["output_fingerprint"] = SHA["path-new"]
        _refresh_fingerprints(candidate)

        outcome = resolve_evidence_lineage(candidate_graph, payload)

        self.assertIsNone(outcome.error)
        self.assertEqual(
            "REVERIFY_TARGETED",
            decision(outcome, "node/root")["disposition"],
        )
        self.assertEqual(
            ["PATH"],
            decision(outcome, "node/root")["changed_edge_types"],
        )
        self.assertEqual(
            "REVERIFY_TARGETED",
            decision(outcome, "node/successor")["disposition"],
        )
        self.assertEqual(
            "REVERIFY_TARGETED",
            decision(outcome, "join/review")["disposition"],
        )
        self.assertEqual("REUSE", decision(outcome, "node/sibling")["disposition"])
        self.assertEqual(
            ["TRANSITIVE_INPUT_CHANGED"],
            decision(outcome, "node/successor")["reason_codes"],
        )

    def test_contract_and_authority_changes_propagate_invalidation(self) -> None:
        candidate_graph = graph()
        for source_id, digest, edge_type, reason in (
            ("contract/core", SHA["contract-new"], "CONTRACT", "CONTRACT_CHANGED"),
            (
                "authority/review",
                SHA["authority-new"],
                "AUTHORITY",
                "AUTHORITY_CHANGED",
            ),
        ):
            with self.subTest(edge_type=edge_type):
                payload = lineage_input(candidate_graph)
                candidate = payload["candidate"]
                nodes = {
                    item["lineage_node_id"]: item
                    for item in candidate["lineage_nodes"]
                }
                nodes[source_id]["output_fingerprint"] = digest
                _refresh_fingerprints(candidate)

                outcome = resolve_evidence_lineage(candidate_graph, payload)

                self.assertIsNone(outcome.error)
                for node_id in ("node/root", "node/successor", "join/review"):
                    self.assertEqual(
                        "INVALIDATE",
                        decision(outcome, node_id)["disposition"],
                    )
                    self.assertEqual(
                        [reason],
                        decision(outcome, node_id)["reason_codes"],
                    )
                self.assertEqual(
                    "REUSE",
                    decision(outcome, "node/sibling")["disposition"],
                )

    def test_candidate_change_invalidates_only_final_descendant(self) -> None:
        candidate_graph = graph()
        payload = lineage_input(candidate_graph)
        candidate = payload["candidate"]
        nodes = {
            item["lineage_node_id"]: item
            for item in candidate["lineage_nodes"]
        }
        nodes["candidate/release"]["output_fingerprint"] = SHA["candidate-new"]
        _refresh_fingerprints(candidate)

        outcome = resolve_evidence_lineage(candidate_graph, payload)

        self.assertEqual(
            "INVALIDATE",
            decision(outcome, "evidence/final")["disposition"],
        )
        self.assertEqual(
            ["CANDIDATE_CHANGED"],
            decision(outcome, "evidence/final")["reason_codes"],
        )
        self.assertEqual("REUSE", decision(outcome, "node/root")["disposition"])

    def test_join_definition_contributors_and_ready_binding_are_targeted(
        self,
    ) -> None:
        candidate_graph = graph()
        mutations = (
            lambda payload: payload["candidate"]["join_integrations"][
                0
            ].__setitem__("definition_fingerprint", "f" * 64),
            lambda payload: payload["baseline"]["join_integrations"][
                0
            ].__setitem__(
                "contributor_node_ids", ["node/root"]
            ),
            lambda payload: payload["candidate"]["join_integrations"][
                0
            ].__setitem__("ready_input_digest", "e" * 64),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                payload = lineage_input(candidate_graph)
                candidate = payload["candidate"]
                mutate(payload)
                join = candidate["join_integrations"][0]
                if join["ready_input_digest"] != SHA["ready"]:
                    candidate["stage4_bindings"][
                        "ready_input_digest"
                    ] = join["ready_input_digest"]
                outcome = resolve_evidence_lineage(candidate_graph, payload)
                self.assertIsNone(outcome.error)
                self.assertEqual(
                    "REVERIFY_TARGETED",
                    decision(outcome, "join/review")["disposition"],
                )

    def test_invalid_input_is_deterministic_immutable_and_has_no_partial_result(
        self,
    ) -> None:
        candidate_graph = graph()
        payload = lineage_input(candidate_graph)
        payload["candidate"]["lineage_edges"][0][
            "source_output_fingerprint"
        ] = "f" * 64
        before_graph = copy.deepcopy(candidate_graph)
        before_payload = copy.deepcopy(payload)

        first = resolve_evidence_lineage(candidate_graph, payload)
        second = resolve_evidence_lineage(candidate_graph, payload)

        self.assertIsNone(first.result)
        self.assertEqual("LINEAGE_INVALID", first.error["error_code"])
        self.assertNotIn("decisions", first.error)
        self.assertEqual(first, second)
        self.assertEqual(before_graph, candidate_graph)
        self.assertEqual(before_payload, payload)

    def test_graph_binding_mismatch_and_cycle_are_error_only(self) -> None:
        candidate_graph = graph()
        mismatch = lineage_input(candidate_graph)
        mismatch["candidate"]["graph_binding"]["graph_digest"] = "f" * 64
        outcome = resolve_evidence_lineage(candidate_graph, mismatch)
        self.assertEqual("GRAPH_BINDING_MISMATCH", outcome.error["error_code"])
        self.assertIsNone(outcome.result)

        cyclic = lineage_input(candidate_graph)
        cyclic["candidate"]["lineage_edges"].append(
            _edge("join/review", "node/root", "JOIN_INTEGRATION")
        )
        _refresh_fingerprints(cyclic["candidate"])
        outcome = resolve_evidence_lineage(candidate_graph, cyclic)
        self.assertEqual("LINEAGE_CYCLE", outcome.error["error_code"])
        self.assertIsNone(outcome.result)

    def test_c0_record_only_reverifies_targeted_consistency_only(self) -> None:
        event = ChangeEvent(
            ChangeClass.C0_RECORD_ONLY,
            changed_paths=("records/status.json",),
        )
        common = dict(
            lane="lane",
            base_sha="base",
            head_sha="head",
            covered_paths=("records",),
            covered_contracts=(),
            command="test",
            dependency_fingerprint="dependency",
            toolchain_fingerprint="toolchain",
            platform="posix",
            authority_version="authority",
            result="PASS",
        )
        consistency = EvidenceFingerprint(
            evidence_id="consistency",
            kind="record-consistency",
            **common,
        )
        semantic = EvidenceFingerprint(
            evidence_id="semantic",
            kind="semantic",
            **common,
        )
        self.assertFalse(assess_evidence(consistency, event).reusable)
        self.assertTrue(assess_evidence(semantic, event).reusable)


if __name__ == "__main__":
    unittest.main()
