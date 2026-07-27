import copy
import hashlib
import json
import re
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
CANONICAL = REPOSITORY / "sagekit/resources/contracts/evidence-lineage/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/evidence-lineage/v1"
RESOURCE_NAMES = (
    "contract.json",
    "input.schema.json",
    "result.schema.json",
    "error.schema.json",
)
STAGE5_CONTRACT_PATHS = {
    f"docs/contracts/evidence-lineage/v1/{name}" for name in RESOURCE_NAMES
} | {
    f"sagekit/resources/contracts/evidence-lineage/v1/{name}"
    for name in RESOURCE_NAMES
}
STAGE5_OWNER_PATHS = {
    "sagekit/evidence.py",
    "sagekit/review.py",
    "tests/fixtures/stage5_observed_failure_corpus_v1.json",
    "tests/unit/test_evidence_lineage.py",
    "tests/unit/test_evidence_lineage_contract_v1.py",
    "tests/unit/test_risk_based_evaluator.py",
    "tests/unit/test_stage5_observed_failure_corpus.py",
}
STAGE5_OWNER_CONTENT_MANIFEST = (
    REPOSITORY / "tests/fixtures/stage5_owner_content_manifest_v1.json"
)
STAGE5_OWNER_DIGESTS = json.loads(
    STAGE5_OWNER_CONTENT_MANIFEST.read_text(encoding="utf-8")
)
STAGE5_OWNED_PATHS = STAGE5_CONTRACT_PATHS | STAGE5_OWNER_PATHS
STAGE5_CONTRACT_RESOURCE_DIGESTS = {
    "contract.json": (
        "240c98234e04e1c97414dae86fadd6a94de16649f71c2dc023e1a2ddf04cbe2a"
    ),
    "error.schema.json": (
        "ed86e040b8fc64e6003dbf163172700faec608d6f73463092005c9ac82aa5019"
    ),
    "input.schema.json": (
        "b57340367797f69001afbbcfbcb337412109f415eac99ea9d9e18a412d309901"
    ),
    "result.schema.json": (
        "46bf939a7b802dde95628079855eb1904e584ff68b574551183ff02c631bae8a"
    ),
}

EDGE_TYPES = {
    "NODE_OUTPUT",
    "JOIN_INTEGRATION",
    "PATH",
    "CONTRACT",
    "AUTHORITY",
    "DEPENDENCY_SET",
    "TOOLCHAIN",
    "PLATFORM",
    "CANDIDATE",
}
DISPOSITIONS = {"REUSE", "REVERIFY_TARGETED", "INVALIDATE"}
ERROR_CODES = {
    "INPUT_INVALID",
    "INPUT_TOO_LARGE",
    "LINEAGE_LIMIT_EXCEEDED",
    "LINEAGE_CYCLE",
    "GRAPH_BINDING_MISMATCH",
    "LINEAGE_INVALID",
    "RESULT_TOO_LARGE",
}
DEPENDENCY_DIGESTS = {
    "docs/contracts/graph/v1/contract.json": (
        "bdd68d8b252de9095831d9d6b802aecee133d85002f1281d1d836ff0a98b52a4"
    ),
    "docs/contracts/graph/v1/graph.schema.json": (
        "b2a6663ffd654c7f54603b1505a6e328d3044f2c34c57717c635144e2e0b5466"
    ),
    "docs/contracts/graph/v1/node-result.schema.json": (
        "a207e510f0b1749ea780494f53d64eca7d7a203c71a6e81db7b12243b5ea6379"
    ),
    "docs/contracts/ready-resolution/v1/contract.json": (
        "9eb5f0f94b3b01f6c71a525bb3ef65ddca31fc9f3fb1eb9b59a1d093aae78f67"
    ),
    "docs/contracts/transition-resolution/v1/contract.json": (
        "385a33f82ea9a65cb90649a4ba7a87fda7eb7035b696766339c691093f7d1291"
    ),
}
NODE_INPUT_DOMAIN = b"sagekit-evidence-lineage-node-input-v1\0"
NODE_INPUT_VECTOR_SHA256 = (
    "150bae360e3f85fb95f4eb5b5f3b82d772eebaabd17a2daa93d57f5b20121b72"
)
FORBIDDEN_PROPERTIES = {
    "prompt",
    "private_reasoning",
    "reasoning",
    "chain_of_thought",
    "transcript",
    "chat_transcript",
    "tool_transcript",
    "stdout",
    "stderr",
    "environment",
    "environment_dump",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "command",
    "callback",
    "payload",
    "runtime_event",
    "state_write",
    "lease",
    "lock",
    "join_satisfied",
    "join_satisfaction",
    "satisfied",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def current_resource_path(relative):
    if relative.startswith("docs/contracts/"):
        relative = relative.replace("docs/contracts/", "sagekit/resources/contracts/", 1)
    return REPOSITORY / relative


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def node_input_fingerprint(graph_binding, incoming_edges):
    projection = {
        "graph_binding": graph_binding,
        "incoming_edges": sorted(
            incoming_edges,
            key=lambda edge: (
                edge["edge_type"],
                edge["source_node_id"],
                edge["source_output_fingerprint"],
            ),
        ),
    }
    return hashlib.sha256(NODE_INPUT_DOMAIN + canonical_bytes(projection)).hexdigest()


def json_equal(left, right):
    if type(left) is not type(right):
        return False
    return left == right


def resolve_ref(root, reference):
    current = root
    for part in reference.removeprefix("#/").split("/"):
        current = current[part.replace("~1", "/").replace("~0", "~")]
    return current


def is_schema_valid(instance, schema, root=None):
    root = schema if root is None else root
    if "$ref" in schema:
        return is_schema_valid(instance, resolve_ref(root, schema["$ref"]), root)
    if "allOf" in schema and not all(
        is_schema_valid(instance, child, root) for child in schema["allOf"]
    ):
        return False
    if "anyOf" in schema and not any(
        is_schema_valid(instance, child, root) for child in schema["anyOf"]
    ):
        return False
    if "oneOf" in schema and sum(
        is_schema_valid(instance, child, root) for child in schema["oneOf"]
    ) != 1:
        return False
    if "not" in schema and is_schema_valid(instance, schema["not"], root):
        return False
    if "if" in schema:
        branch = "then" if is_schema_valid(instance, schema["if"], root) else "else"
        if branch in schema and not is_schema_valid(instance, schema[branch], root):
            return False
    if "const" in schema and not json_equal(instance, schema["const"]):
        return False
    if "enum" in schema and not any(
        json_equal(instance, item) for item in schema["enum"]
    ):
        return False

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        checks = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "integer": lambda value: type(value) is int,
            "number": lambda value: type(value) in (int, float),
            "boolean": lambda value: isinstance(value, bool),
            "null": lambda value: value is None,
        }
        if not any(checks[name](instance) for name in allowed):
            return False

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            return False
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            return False
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            return False

    if type(instance) in (int, float):
        if "minimum" in schema and instance < schema["minimum"]:
            return False
        if "maximum" in schema and instance > schema["maximum"]:
            return False

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            return False
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            return False
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in instance]
            if len(encoded) != len(set(encoded)):
                return False
        if "items" in schema and not all(
            is_schema_valid(item, schema["items"], root) for item in instance
        ):
            return False
        if "contains" in schema:
            count = sum(
                is_schema_valid(item, schema["contains"], root) for item in instance
            )
            if count < schema.get("minContains", 1):
                return False
            if "maxContains" in schema and count > schema["maxContains"]:
                return False

    if isinstance(instance, dict):
        if len(instance) < schema.get("minProperties", 0):
            return False
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            return False
        if any(name not in instance for name in schema.get("required", [])):
            return False
        properties = schema.get("properties", {})
        for name, value in instance.items():
            if "propertyNames" in schema and not is_schema_valid(
                name, schema["propertyNames"], root
            ):
                return False
            if name in properties and not is_schema_valid(
                value, properties[name], root
            ):
                return False
            if name not in properties and schema.get("additionalProperties") is False:
                return False
            if name not in properties and isinstance(
                schema.get("additionalProperties"), dict
            ) and not is_schema_valid(value, schema["additionalProperties"], root):
                return False
    return True


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def valid_input():
    graph = {
        "graph_id": "graph/spec",
        "graph_generation": 7,
        "graph_digest": "a" * 64,
    }
    incoming = [
        {
            "edge_type": "CONTRACT",
            "source_node_id": "contract/graph",
            "source_output_fingerprint": "b" * 64,
        },
        {
            "edge_type": "NODE_OUTPUT",
            "source_node_id": "node/build",
            "source_output_fingerprint": "c" * 64,
        },
    ]
    verify_input = node_input_fingerprint(graph, incoming)
    snapshot = {
        "graph_binding": graph,
        "stage4_bindings": {
            "ready_input_digest": "d" * 64,
            "transition_bindings": [
                {
                    "node_id": "node/build",
                    "transition_input_digest": "e" * 64,
                    "node_result_digest": "c" * 64,
                },
                {
                    "node_id": "node/verify",
                    "transition_input_digest": "f" * 64,
                    "node_result_digest": "1" * 64,
                },
            ],
        },
        "lineage_nodes": [
            {
                "lineage_node_id": "contract/graph",
                "owner_kind": "CONTRACT",
                "owner_id": "graph-contract-v1",
                "input_fingerprint": "2" * 64,
                "output_fingerprint": "b" * 64,
            },
            {
                "lineage_node_id": "node/build",
                "owner_kind": "GRAPH_NODE",
                "owner_id": "node/build",
                "input_fingerprint": "3" * 64,
                "output_fingerprint": "c" * 64,
            },
            {
                "lineage_node_id": "node/verify",
                "owner_kind": "GRAPH_NODE",
                "owner_id": "node/verify",
                "input_fingerprint": verify_input,
                "output_fingerprint": "1" * 64,
            },
            {
                "lineage_node_id": "candidate/release",
                "owner_kind": "CANDIDATE",
                "owner_id": "candidate/release",
                "input_fingerprint": "4" * 64,
                "output_fingerprint": "5" * 64,
            },
            {
                "lineage_node_id": "evidence/final",
                "owner_kind": "EVIDENCE",
                "owner_id": "evidence/final",
                "input_fingerprint": "6" * 64,
                "output_fingerprint": "7" * 64,
            },
        ],
        "lineage_edges": [
            {
                "source_node_id": "contract/graph",
                "target_node_id": "node/verify",
                "edge_type": "CONTRACT",
                "source_output_fingerprint": "b" * 64,
                "target_input_fingerprint": verify_input,
            },
            {
                "source_node_id": "node/build",
                "target_node_id": "node/verify",
                "edge_type": "NODE_OUTPUT",
                "source_output_fingerprint": "c" * 64,
                "target_input_fingerprint": verify_input,
            },
            {
                "source_node_id": "candidate/release",
                "target_node_id": "evidence/final",
                "edge_type": "CANDIDATE",
                "source_output_fingerprint": "5" * 64,
                "target_input_fingerprint": "6" * 64,
            },
        ],
        "join_integrations": [
            {
                "join_id": "join/review",
                "policy": "manual-gate",
                "definition_fingerprint": "8" * 64,
                "contributor_node_ids": ["node/build", "node/verify"],
                "ready_input_digest": "d" * 64,
                "external_decision_refs": [
                    "authority/reviewer",
                    "evidence/review-decision",
                ],
            }
        ],
        "final_evidence_node_id": "evidence/final",
    }
    return {
        "schema_id": "urn:sagekit:evidence-lineage:v1:input",
        "schema_version": 1,
        "baseline": snapshot,
        "candidate": copy.deepcopy(snapshot),
    }


def valid_result():
    return {
        "schema_id": "urn:sagekit:evidence-lineage:v1:result",
        "schema_version": 1,
        "graph_id": "graph/spec",
        "graph_generation": 7,
        "graph_digest": "a" * 64,
        "decisions": {
            "node/build": {
                "disposition": "REUSE",
                "input_fingerprint": "3" * 64,
                "output_fingerprint": "c" * 64,
                "changed_edge_types": [],
                "reason_codes": ["FINGERPRINTS_MATCH"],
            },
            "node/verify": {
                "disposition": "REVERIFY_TARGETED",
                "input_fingerprint": "9" * 64,
                "output_fingerprint": "1" * 64,
                "changed_edge_types": ["NODE_OUTPUT"],
                "reason_codes": ["TRANSITIVE_INPUT_CHANGED"],
            },
        },
        "final_evidence_node_id": "evidence/final",
    }


class EvidenceLineageContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_json(CANONICAL / "contract.json")
        cls.input_schema = load_json(CANONICAL / "input.schema.json")
        cls.result_schema = load_json(CANONICAL / "result.schema.json")
        cls.error_schema = load_json(CANONICAL / "error.schema.json")

    def test_stage5_owned_path_sets_are_disjoint_and_resolve_to_fifteen_files(self):
        self.assertTrue(STAGE5_CONTRACT_PATHS.isdisjoint(STAGE5_OWNER_PATHS))
        self.assertEqual(
            STAGE5_CONTRACT_PATHS | STAGE5_OWNER_PATHS,
            STAGE5_OWNED_PATHS,
        )
        self.assertEqual(15, len(STAGE5_OWNED_PATHS))
        missing = {
            path for path in STAGE5_OWNED_PATHS if not current_resource_path(path).is_file()
        }
        self.assertEqual(set(), missing)

    def test_stage5_owner_content_manifest_binds_every_owner_file(self):
        self.assertEqual(STAGE5_OWNER_PATHS, set(STAGE5_OWNER_DIGESTS))
        for path, expected in STAGE5_OWNER_DIGESTS.items():
            if path in {
                "tests/unit/test_evidence_lineage_contract_v1.py",
                "tests/unit/test_stage5_observed_failure_corpus.py",
            }:
                continue
            self.assertEqual(expected, sha256(current_resource_path(path)), path)

    def test_stage5_contract_resources_match_fixed_canonical_digests(self):
        self.assertEqual(set(RESOURCE_NAMES), set(STAGE5_CONTRACT_RESOURCE_DIGESTS))
        for name, expected in STAGE5_CONTRACT_RESOURCE_DIGESTS.items():
            self.assertEqual(expected, sha256(CANONICAL / name), name)

    def test_resources_are_valid_json_byte_identical_and_schema_digest_bound(self):
        resource_keys = {
            "input_schema": "input.schema.json",
            "result_schema": "result.schema.json",
            "error_schema": "error.schema.json",
        }
        for name in RESOURCE_NAMES:
            self.assertEqual(load_json(CANONICAL / name), load_json(PACKAGED / name))
            self.assertEqual((CANONICAL / name).read_bytes(), (PACKAGED / name).read_bytes())
        for key, name in resource_keys.items():
            self.assertEqual(
                sha256(CANONICAL / name),
                self.contract["resources"][key]["canonical_sha256"],
            )
        self.assertIn(
            "byte-identical", self.contract["packaged_mirror"]["expectation"]
        )

    def test_final_stage4_dependency_digests_are_frozen_without_redefinition(self):
        records = self.contract["dependencies"]
        observed = {}
        for record in records.values():
            path = record["resource"]
            if path in DEPENDENCY_DIGESTS:
                observed[path] = record["canonical_sha256"]
        self.assertEqual(DEPENDENCY_DIGESTS, observed)
        for path, expected in DEPENDENCY_DIGESTS.items():
            self.assertEqual(expected, sha256(current_resource_path(path)), path)
        for record in records.values():
            self.assertEqual(
                record["canonical_sha256"],
                sha256(current_resource_path(record["resource"])),
                record["resource"],
            )
        digest_boundary = self.contract["fingerprint_semantics"][
            "existing_digest_ownership"
        ]
        for phrase in (
            "validate_graph_contract.semantic_digest",
            "Ready Resolution input_digest",
            "Transition Resolution input_digest",
            "Node Result digest",
            "does not redefine",
        ):
            self.assertIn(phrase, digest_boundary)

    def test_schema_ids_and_required_fields_are_stable(self):
        self.assertEqual(
            "urn:sagekit:evidence-lineage:v1", self.contract["contract_id"]
        )
        self.assertEqual(
            "urn:sagekit:evidence-lineage:v1:input", self.input_schema["$id"]
        )
        self.assertEqual(
            "urn:sagekit:evidence-lineage:v1:result", self.result_schema["$id"]
        )
        self.assertEqual(
            "urn:sagekit:evidence-lineage:v1:error", self.error_schema["$id"]
        )
        self.assertEqual(
            {
                "schema_id",
                "schema_version",
                "baseline",
                "candidate",
            },
            set(self.input_schema["required"]),
        )
        snapshot_required = {
            "graph_binding",
            "stage4_bindings",
            "lineage_nodes",
            "lineage_edges",
            "join_integrations",
            "final_evidence_node_id",
        }
        self.assertEqual(
            snapshot_required,
            set(self.input_schema["$defs"]["lineage_snapshot"]["required"]),
        )

    def test_schemas_are_closed_and_every_collection_is_bounded(self):
        for schema in (self.input_schema, self.result_schema, self.error_schema):
            objects = [
                item
                for item in walk(schema)
                if isinstance(item, dict) and item.get("type") == "object"
            ]
            arrays = [
                item
                for item in walk(schema)
                if isinstance(item, dict) and item.get("type") == "array"
            ]
            self.assertTrue(objects)
            self.assertTrue(arrays)
            for object_schema in objects:
                if "propertyNames" in object_schema:
                    self.assertIsInstance(
                        object_schema.get("additionalProperties"), dict
                    )
                else:
                    self.assertIs(False, object_schema.get("additionalProperties"))
            for array_schema in arrays:
                self.assertIn("maxItems", array_schema)

    def test_valid_instances_and_unknown_fields(self):
        candidate = valid_input()
        self.assertTrue(is_schema_valid(candidate, self.input_schema))
        self.assertTrue(is_schema_valid(valid_result(), self.result_schema))
        candidate["unknown"] = True
        self.assertFalse(is_schema_valid(candidate, self.input_schema))
        nested = valid_input()
        nested["candidate"]["lineage_nodes"][0]["prompt"] = "not lineage"
        self.assertFalse(is_schema_valid(nested, self.input_schema))

    def test_input_requires_two_complete_comparable_lineages(self):
        candidate = valid_input()
        del candidate["baseline"]
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

        candidate = valid_input()
        del candidate["candidate"]["lineage_edges"]
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

        candidate = valid_input()
        candidate["candidate"]["lineage_nodes"][1]["output_fingerprint"] = "9" * 64
        self.assertTrue(is_schema_valid(candidate, self.input_schema))
        self.assertNotEqual(
            candidate["baseline"]["lineage_nodes"],
            candidate["candidate"]["lineage_nodes"],
        )

    def test_typed_edges_and_dispositions_are_exact(self):
        edge_enum = self.input_schema["$defs"]["edge"]["properties"]["edge_type"][
            "enum"
        ]
        disposition_enum = self.result_schema["$defs"]["decision"]["properties"][
            "disposition"
        ]["enum"]
        self.assertEqual(EDGE_TYPES, set(edge_enum))
        self.assertEqual(DISPOSITIONS, set(disposition_enum))
        self.assertEqual(
            ERROR_CODES, set(self.error_schema["properties"]["error_code"]["enum"])
        )
        owners = self.contract["lineage_validation"]["typed_edge_owners"]
        self.assertEqual(EDGE_TYPES, set(owners))
        for edge_type, owner_kind in (
            ("NODE_OUTPUT", "GRAPH_NODE"),
            ("JOIN_INTEGRATION", "JOIN"),
            ("PATH", "PATH"),
            ("CONTRACT", "CONTRACT"),
            ("AUTHORITY", "AUTHORITY"),
            ("DEPENDENCY_SET", "DEPENDENCY_SET"),
            ("TOOLCHAIN", "TOOLCHAIN"),
            ("PLATFORM", "PLATFORM"),
            ("CANDIDATE", "CANDIDATE"),
        ):
            self.assertIn(owner_kind, owners[edge_type])

    def test_final_evidence_requires_exactly_one_candidate_edge(self):
        candidate = valid_input()
        self.assertTrue(is_schema_valid(candidate, self.input_schema))
        candidate["candidate"]["lineage_edges"] = [
            edge
            for edge in candidate["candidate"]["lineage_edges"]
            if edge["edge_type"] != "CANDIDATE"
        ]
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

        candidate = valid_input()
        candidate["candidate"]["lineage_edges"].append(
            {
                "source_node_id": "candidate/release",
                "target_node_id": "evidence/final",
                "edge_type": "CANDIDATE",
                "source_output_fingerprint": "5" * 64,
                "target_input_fingerprint": "6" * 64,
            }
        )
        self.assertFalse(is_schema_valid(candidate, self.input_schema))
        final_rule = self.contract["lineage_validation"]["final_evidence"]
        self.assertIn("exactly one", final_rule)
        self.assertIn("CANDIDATE", final_rule)

    def test_join_integration_binds_sources_without_copying_satisfaction(self):
        join = self.input_schema["$defs"]["join_integration"]
        self.assertEqual(
            {
                "join_id",
                "policy",
                "definition_fingerprint",
                "contributor_node_ids",
                "ready_input_digest",
                "external_decision_refs",
            },
            set(join["required"]),
        )
        serialized = json.dumps(join, sort_keys=True).lower()
        for forbidden in ("satisfied", "satisfaction", "disposition", "decision"):
            self.assertNotIn(f'"{forbidden}"', serialized)
        boundary = self.contract["join_integration"]["boundary"]
        for phrase in (
            "Graph join definition",
            "contributors",
            "Stage 4 Ready",
            "external decision",
            "does not copy join satisfaction",
        ):
            self.assertIn(phrase, boundary)

    def test_join_policy_conditionally_binds_external_refs(self):
        candidate = valid_input()
        join = candidate["candidate"]["join_integrations"][0]
        join["policy"] = "all-required"
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

        candidate = valid_input()
        join = candidate["candidate"]["join_integrations"][0]
        join["external_decision_refs"] = []
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

        candidate = valid_input()
        join = candidate["candidate"]["join_integrations"][0]
        join["policy"] = "corrective-join"
        self.assertTrue(is_schema_valid(candidate, self.input_schema))

        candidate = valid_input()
        join = candidate["candidate"]["join_integrations"][0]
        join["policy"] = "first-success"
        join["external_decision_refs"] = []
        self.assertTrue(is_schema_valid(candidate, self.input_schema))

    def test_bounded_refs_reject_case_insensitive_external_locations(self):
        forbidden_refs = (
            "FILE:review.json",
            "File:///tmp/review.json",
            "HTTP://example.test/review",
            "hTtPs://example.test/review",
            "UNC:server/share/review",
            "C:/review.json",
            "c:\\review.json",
            "/tmp/review.json",
            "\\\\server\\share\\review.json",
        )
        for value in forbidden_refs:
            with self.subTest(value=value):
                candidate = valid_input()
                candidate["candidate"]["join_integrations"][0][
                    "external_decision_refs"
                ] = [value]
                self.assertFalse(is_schema_valid(candidate, self.input_schema))

    def test_result_decisions_are_identity_keyed_and_semantically_consistent(self):
        schema = self.result_schema["properties"]["decisions"]
        self.assertEqual("object", schema["type"])
        self.assertEqual(10000, schema["maxProperties"])
        self.assertTrue(is_schema_valid(valid_result(), self.result_schema))

        invalid = valid_result()
        invalid["decisions"]["node/build"]["reason_codes"] = [
            "DIRECT_INPUT_CHANGED"
        ]
        self.assertFalse(is_schema_valid(invalid, self.result_schema))

        invalid = valid_result()
        invalid["decisions"]["node/build"]["changed_edge_types"] = ["PATH"]
        self.assertFalse(is_schema_valid(invalid, self.result_schema))

        invalid = valid_result()
        invalid["decisions"]["node/verify"]["changed_edge_types"] = ["CONTRACT"]
        self.assertFalse(is_schema_valid(invalid, self.result_schema))

        invalid = valid_result()
        invalid["decisions"]["node/verify"]["disposition"] = "INVALIDATE"
        self.assertFalse(is_schema_valid(invalid, self.result_schema))

    def test_error_code_and_message_code_are_conditionally_bound(self):
        pairs = {
            "INPUT_INVALID": "STRICT_INPUT_REQUIRED",
            "INPUT_TOO_LARGE": "INPUT_BYTE_BUDGET_EXCEEDED",
            "LINEAGE_LIMIT_EXCEEDED": "STRUCTURAL_LIMIT_EXCEEDED",
            "LINEAGE_CYCLE": "ACYCLIC_LINEAGE_REQUIRED",
            "GRAPH_BINDING_MISMATCH": "GRAPH_BINDING_REQUIRED",
            "LINEAGE_INVALID": "VALID_LINEAGE_REQUIRED",
            "RESULT_TOO_LARGE": "RESULT_BYTE_BUDGET_EXCEEDED",
        }
        self.assertEqual(pairs, self.contract["error_code_message_code"])
        for error_code, message_code in pairs.items():
            valid = {
                "schema_id": "urn:sagekit:evidence-lineage:v1:error",
                "schema_version": 1,
                "error_code": error_code,
                "message_code": message_code,
                "issues": [],
            }
            self.assertTrue(is_schema_valid(valid, self.error_schema))
            invalid = copy.deepcopy(valid)
            invalid["message_code"] = "STRICT_INPUT_REQUIRED" if error_code != "INPUT_INVALID" else "VALID_LINEAGE_REQUIRED"
            self.assertFalse(is_schema_valid(invalid, self.error_schema))

    def test_fixed_cross_language_node_input_vector(self):
        vector = self.contract["fingerprint_semantics"]["fixed_vectors"][0]
        self.assertEqual("cross-language-node-input-001", vector["vector_id"])
        self.assertEqual(
            NODE_INPUT_DOMAIN.hex(), vector["domain_separator_utf8_hex"]
        )
        self.assertEqual(
            NODE_INPUT_VECTOR_SHA256,
            node_input_fingerprint(
                vector["graph_binding"], vector["incoming_edges"]
            ),
        )
        self.assertEqual(NODE_INPUT_VECTOR_SHA256, vector["input_fingerprint"])
        comparison = self.contract["fingerprint_semantics"]["fixed_vectors"][1]
        self.assertEqual(
            "baseline-candidate-comparison-001", comparison["vector_id"]
        )
        self.assertNotEqual(
            comparison["baseline"]["node_output_fingerprint"],
            comparison["candidate"]["node_output_fingerprint"],
        )
        self.assertNotEqual(
            comparison["baseline"]["candidate_output_fingerprint"],
            comparison["candidate"]["candidate_output_fingerprint"],
        )
        self.assertEqual(
            {
                "local_change_edge_type": "NODE_OUTPUT",
                "local_disposition": "REVERIFY_TARGETED",
                "final_change_edge_type": "CANDIDATE",
                "final_disposition": "INVALIDATE",
            },
            comparison["expected"],
        )

    def test_key_and_normalized_edge_order_invariance(self):
        graph = {
            "graph_id": "graph/跨语言",
            "graph_generation": 7,
            "graph_digest": "0" * 64,
        }
        edges = [
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
        ]
        reordered_graph = {
            "graph_digest": "0" * 64,
            "graph_generation": 7,
            "graph_id": "graph/跨语言",
        }
        self.assertEqual(
            node_input_fingerprint(graph, edges),
            node_input_fingerprint(reordered_graph, list(reversed(edges))),
        )
        changed = copy.deepcopy(edges)
        changed[0]["source_output_fingerprint"] = "3" * 64
        self.assertNotEqual(
            node_input_fingerprint(graph, edges),
            node_input_fingerprint(graph, changed),
        )
        rules = self.contract["fingerprint_semantics"]["normalization"]
        self.assertIn("Sort object keys", rules["object_keys"])
        self.assertIn("incoming edges", rules["incoming_edges"])
        self.assertIn("preserved", rules["other_arrays"])

    def test_local_change_propagation_is_targeted(self):
        rule = self.contract["change_classification"]
        self.assertEqual(
            [
                "NODE_OUTPUT",
                "JOIN_INTEGRATION",
                "PATH",
                "DEPENDENCY_SET",
                "TOOLCHAIN",
                "PLATFORM",
            ],
            rule["targeted_reverification_edge_types"],
        )
        self.assertEqual(
            ["CONTRACT", "AUTHORITY", "CANDIDATE"],
            rule["invalidation_edge_types"],
        )
        local = rule["locality_rule"]
        self.assertIn("transitive descendants", local)
        self.assertIn("unrelated", local)
        self.assertIn("REUSE", local)

    def test_graph_identity_or_generation_change_forbids_reuse(self):
        rule = self.contract["change_classification"]["graph_identity_rule"]
        for phrase in (
            "graph_id",
            "graph_generation",
            "REUSE",
            "forbidden",
            "INVALIDATE",
        ):
            self.assertIn(phrase, rule)
        digest_rule = self.contract["lineage_validation"]["graph_binding"]
        self.assertIn("GRAPH_BINDING_MISMATCH", digest_rule)
        self.assertIn("no Result", digest_rule)

    def test_cycle_invalid_and_oversize_are_error_only(self):
        failures = self.contract["failure_semantics"]
        for key in (
            "LINEAGE_CYCLE",
            "LINEAGE_INVALID",
            "INPUT_TOO_LARGE",
            "LINEAGE_LIMIT_EXCEEDED",
            "RESULT_TOO_LARGE",
        ):
            text = failures[key]
            self.assertIn("Error", text)
            self.assertIn("no partial Result", text)
        error_serialized = json.dumps(self.error_schema, sort_keys=True)
        for name in ("decisions", "disposition", "final_evidence_node_id"):
            self.assertNotIn(f'"{name}"', error_serialized)
        completeness = self.contract["lineage_validation"]["result_completeness"]
        self.assertIn("exactly one decision", completeness)
        self.assertIn("every admitted lineage_node_id", completeness)
        self.assertIn("never returns a reusable subset", completeness)
        self.assertEqual(
            [
                "strict_json",
                "bounded_input_canonical_bytes",
                "schema_shape_and_direct_cardinality",
                "candidate_graph_binding",
                "identity_uniqueness",
                "referential_integrity",
                "stage4_digest_binding",
                "final_candidate_edge",
                "edge_fingerprint_binding",
                "acyclicity",
                "complete_change_classification",
                "bounded_complete_result",
            ],
            self.contract["deterministic_validation_order"],
        )
        classification = self.contract["validation_precedence"]
        self.assertEqual("INPUT_TOO_LARGE", classification["byte_over_shape"])
        self.assertEqual("LINEAGE_LIMIT_EXCEEDED", classification["cardinality"])
        self.assertEqual("LINEAGE_CYCLE", classification["cycle"])
        self.assertIn("only after", classification["cycle_scope"])

    def test_bytes_and_cardinality_are_explicit_and_inclusive(self):
        budgets = self.contract["admission_bounds"]
        self.assertEqual(8_388_608, budgets["max_input_canonical_bytes"])
        self.assertEqual(8_388_608, budgets["max_result_canonical_bytes"])
        self.assertEqual(1_048_576, budgets["max_error_canonical_bytes"])
        self.assertEqual(10_000, budgets["max_lineage_nodes"])
        self.assertEqual(50_000, budgets["max_lineage_edges"])
        self.assertEqual(10_000, budgets["max_join_integrations"])
        self.assertEqual(100, budgets["max_error_issues"])
        self.assertIn("inclusive", self.contract["admission_semantics"])
        self.assertIn("bounded", self.contract["admission_semantics"])

    def test_privacy_allowlist_and_non_goals_are_closed(self):
        property_names = {
            name
            for item in walk(
                [self.input_schema, self.result_schema, self.error_schema]
            )
            if isinstance(item, dict)
            for name in item.get("properties", {})
        }
        self.assertFalse(property_names & FORBIDDEN_PROPERTIES)
        privacy = self.contract["semantic_boundaries"]["privacy"]
        for phrase in (
            "private reasoning",
            "transcript",
            "stdout",
            "stderr",
            "credentials",
            "secrets",
            "absolute local paths",
        ):
            self.assertIn(phrase, privacy)
        non_goals = self.contract["semantic_boundaries"]["non_goals"]
        for phrase in (
            "CLI",
            "scheduler",
            "database",
            "Stage 6",
            "execution authority",
        ):
            self.assertIn(phrase, non_goals)


if __name__ == "__main__":
    unittest.main()
