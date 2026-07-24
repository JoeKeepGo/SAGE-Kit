import copy
import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "e571849149d614f4fb365bc2255185f1263ab535"
CANONICAL = REPOSITORY / "docs/contracts/ready-resolution/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/ready-resolution/v1"
GRAPH_SCHEMA = REPOSITORY / "docs/contracts/graph/v1/graph.schema.json"
RESOURCE_NAMES = (
    "contract.json",
    "error.schema.json",
    "input.schema.json",
    "result.schema.json",
)
EXPECTED_STAGE4A_PATHS = {
    "docs/contracts/ready-resolution/v1/contract.json",
    "docs/contracts/ready-resolution/v1/error.schema.json",
    "docs/contracts/ready-resolution/v1/result.schema.json",
    "sagekit/resources/contracts/ready-resolution/v1/contract.json",
    "sagekit/resources/contracts/ready-resolution/v1/error.schema.json",
    "sagekit/resources/contracts/ready-resolution/v1/result.schema.json",
    "tests/unit/test_ready_resolution_contract_v1.py",
}
DEPENDENCY_DIGESTS = {
    "docs/contracts/graph/v1/contract.json": "fee6c97a067752e75755cf166cd94322cbe3775c298e474781f8814564356c76",
    "docs/contracts/graph/v1/graph.schema.json": "510f9d4a960aba78f80ac0ec35ac37504d992702528acad3c9f96279cab1824e",
    "docs/contracts/graph/v1/node-result.schema.json": "a207e510f0b1749ea780494f53d64eca7d7a203c71a6e81db7b12243b5ea6379",
    "docs/contracts/runtime-state/v1/contract.json": "a27806a732dbf60b9c38b7f410e62ce6d93a38c9a99d222c27241ac57c6ed976",
    "docs/contracts/runtime-state/v1/state.schema.json": "0bc618412e1e2a8fbdb4691840477460294f38bf76b46dccef250979af29ce2e",
    "docs/contracts/runtime-state/v1/event.schema.json": "d7419489668ac25172e311d6ef53232746e7c778cd6af3ff2391765d13f6f4a9",
}
BASELINE_SCHEMA_DIGESTS = {
    "input.schema.json": "fc6d9edfdd50c66959ed55c59cda6b78cd7ac44b508081ce896aa2efdcc2b481",
    "result.schema.json": "35fc3245998601bd0d5e4d7cff42a5a1be35dfacd4729668c1286cdb340ddf4b",
    "error.schema.json": "a373a5bd3c136a09bd1f80426fdbf954f8e4d2a5b090a579d327aa90b1e589d7",
}
PROTECTED_GIT_BLOBS = {
    "docs/contracts/graph/v1/contract.json": "742ce89bb40b32a85fa9075db7c6a18bf88a81b0",
    "docs/contracts/graph/v1/graph.schema.json": "ac832ee4b0db701fd4cb38581f4e882ea6f9eceb",
    "docs/contracts/graph/v1/node-result.schema.json": "a64b1aaec02bb6d35d024e12508c2cf40c29ecf8",
    "docs/contracts/runtime-state/v1/contract.json": "f2c981da36933c53a6aca35bba54c22c63c2103e",
    "docs/contracts/runtime-state/v1/event.schema.json": "15fb63092c9848b0b81a70bca3ddbb2de145ba39",
    "docs/contracts/runtime-state/v1/state.schema.json": "1f2484dcc9f1c1a20cbed27e52bef31fa447c5ae",
    "sagekit/resources/contracts/graph/v1/contract.json": "742ce89bb40b32a85fa9075db7c6a18bf88a81b0",
    "sagekit/resources/contracts/graph/v1/graph.schema.json": "ac832ee4b0db701fd4cb38581f4e882ea6f9eceb",
    "sagekit/resources/contracts/graph/v1/node-result.schema.json": "a64b1aaec02bb6d35d024e12508c2cf40c29ecf8",
    "sagekit/resources/contracts/runtime-state/v1/contract.json": "f2c981da36933c53a6aca35bba54c22c63c2103e",
    "sagekit/resources/contracts/runtime-state/v1/event.schema.json": "15fb63092c9848b0b81a70bca3ddbb2de145ba39",
    "sagekit/resources/contracts/runtime-state/v1/state.schema.json": "1f2484dcc9f1c1a20cbed27e52bef31fa447c5ae",
}
INPUT_DIGEST_DOMAIN = b"sagekit-ready-resolution-input-v1\0"
ERROR_CODES = {
    "REQUIRED_INPUT_INVALID",
    "GRAPH_INVALID",
    "GRAPH_BINDING_MISMATCH",
    "INPUT_TOO_LARGE",
    "GRAPH_TOO_LARGE",
    "RESOLUTION_LIMIT_EXCEEDED",
    "RESULT_TOO_LARGE",
}
NODE_STATUSES = {
    "PENDING",
    "READY",
    "RUNNING",
    "WAITING_RESOURCE",
    "SUCCEEDED",
    "NO_ACTION_REQUIRED",
    "FAILED",
    "NEEDS_CORRECTION",
    "HANDOFF",
    "BLOCKED",
    "CANCELLED",
    "DONE_WITH_CONCERNS",
}
RESOURCE_AVAILABILITY = {"AVAILABLE", "BUSY", "UNAVAILABLE", "UNKNOWN"}
EXTERNAL_DECISIONS = {"PENDING", "SATISFIED", "REJECTED"}
NODE_DISPOSITIONS = {
    "READY",
    "WAITING_DEPENDENCY",
    "WAITING_RESOURCE",
    "IN_PROGRESS",
    "NEEDS_CORRECTION",
    "HANDOFF_REQUIRED",
    "BLOCKED",
    "COMPLETED",
    "CANCELLED",
}
JOIN_DISPOSITIONS = {
    "SATISFIED",
    "WAITING_NODE",
    "REQUIRES_EXTERNAL_DECISION",
    "REJECTED",
    "BLOCKED",
}
GRAPH_DISPOSITIONS = {
    "READY",
    "IN_PROGRESS",
    "WAITING",
    "NEEDS_CORRECTION",
    "HANDOFF_REQUIRED",
    "BLOCKED",
    "COMPLETED",
}
REQUIRED_REASON_CODES = {
    "DEPENDENCY_PENDING",
    "DEPENDENCY_FAILED",
    "RESOURCE_BUSY",
    "RESOURCE_UNAVAILABLE",
    "RESOURCE_UNKNOWN",
    "NODE_RUNNING",
    "NODE_NEEDS_CORRECTION",
    "NODE_HANDOFF",
    "NODE_BLOCKED",
    "NODE_CANCELLED",
    "JOIN_NODE_PENDING",
    "JOIN_NODE_FAILED",
    "EXTERNAL_DECISION_MISSING",
    "EXTERNAL_DECISION_REJECTED",
}
SUMMARY_FIELDS = {
    "node_decision_count",
    "join_decision_count",
    "ready_node_count",
    "waiting_dependency_node_count",
    "waiting_resource_node_count",
    "in_progress_node_count",
    "needs_correction_node_count",
    "handoff_required_node_count",
    "blocked_node_count",
    "completed_node_count",
    "cancelled_node_count",
    "satisfied_join_count",
    "waiting_node_join_count",
    "requires_external_decision_join_count",
    "rejected_join_count",
    "blocked_join_count",
}
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
    "environment_dump",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "process_handle",
    "agent_handle",
    "tool_handle",
    "callback",
    "command",
    "execution_command",
    "absolute_local_path",
    "payload",
    "arbitrary_payload",
    "project_history",
    "complete_project_history",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical_json_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def minimal_node(node_id="node-0", *, depends_on=None, resources=None):
    return {
        "id": node_id,
        "role": "contract-vector",
        "depends_on": [] if depends_on is None else depends_on,
        "permission": "READ_ONLY_REVIEW",
        "verifier": "focused-contract-vector",
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": [] if resources is None else resources,
        "classification": "required",
    }


def minimal_graph(*, graph_id="graph-vector", nodes=None, joins=None):
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": graph_id,
        "generation": 1,
        "source_authority": {
            "identity": "Stage 4A-C4 contract vector",
            "reference": "ready-resolution/cardinality-corrective",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [minimal_node()] if nodes is None else nodes,
        "joins": [] if joins is None else joins,
    }


def reference_graph_admission_error(graph, graph_canonical_bytes, bounds):
    """Independent admission-vector logic only; this is not a product resolver."""
    if graph_canonical_bytes > bounds["max_graph_canonical_bytes"]:
        return "GRAPH_TOO_LARGE"
    if len(graph["nodes"]) > bounds["max_graph_nodes"]:
        return "RESOLUTION_LIMIT_EXCEEDED"
    if len(graph["joins"]) > bounds["max_graph_joins"]:
        return "RESOLUTION_LIMIT_EXCEEDED"
    for node in graph["nodes"]:
        if len(node["depends_on"]) > bounds["max_node_dependencies"]:
            return "RESOLUTION_LIMIT_EXCEEDED"
        if len(node["resources"]) > bounds["max_node_resources"]:
            return "RESOLUTION_LIMIT_EXCEEDED"
    for join in graph["joins"]:
        if len(join["requires"]) > bounds["max_join_requires"]:
            return "RESOLUTION_LIMIT_EXCEEDED"
    return None


def rejected_blocking_refs(authority_ref, evidence_refs):
    """Reference union vector; preserves input values and does not resolve a Graph."""
    return list(dict.fromkeys((authority_ref, *evidence_refs)))


def semantic_input_digest(value, schema):
    """Independent contract-vector implementation; this is not a product resolver."""
    if not is_schema_valid(value, schema):
        raise ValueError("strict input validation must succeed before digest")
    for array_name, identity_name in (
        ("node_states", "node_id"),
        ("resource_availability", "resource_id"),
        ("external_join_decisions", "join_id"),
    ):
        identities = [item[identity_name] for item in value[array_name]]
        if len(identities) != len(set(identities)):
            raise ValueError(f"duplicate {identity_name}")

    normalized = copy.deepcopy(value)
    for array_name, identity_name in (
        ("node_states", "node_id"),
        ("resource_availability", "resource_id"),
        ("external_join_decisions", "join_id"),
    ):
        normalized[array_name].sort(key=lambda item: item[identity_name])
        for item in normalized[array_name]:
            if "evidence_refs" in item:
                item["evidence_refs"].sort()
    return hashlib.sha256(INPUT_DIGEST_DOMAIN + canonical_json_bytes(normalized)).hexdigest()


def changed_paths_since_baseline():
    tracked = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--no-renames",
            "--diff-filter=ACDMRTUXB",
            BASELINE_COMMIT,
            "--",
        ],
        cwd=REPOSITORY,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPOSITORY,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    return {path.replace("\\", "/") for path in (*tracked, *untracked)}


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def object_schemas(value):
    for item in walk(value):
        if isinstance(item, dict) and item.get("type") == "object":
            yield item


def property_names(value):
    return {
        name.lower()
        for item in walk(value)
        if isinstance(item, dict)
        for name in item.get("properties", {})
    }


def json_equal(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def resolve_local_ref(root, reference):
    if not reference.startswith("#/"):
        raise AssertionError(f"non-local schema reference: {reference}")
    value = root
    for component in reference[2:].split("/"):
        value = value[component.replace("~1", "/").replace("~0", "~")]
    return value


def is_schema_valid(instance, schema, root=None):
    """Dependency-free evaluator for the schema keywords exercised by these tests."""
    root = schema if root is None else root
    if isinstance(schema, bool):
        return schema
    if "$ref" in schema and not is_schema_valid(instance, resolve_local_ref(root, schema["$ref"]), root):
        return False
    if "allOf" in schema and not all(is_schema_valid(instance, child, root) for child in schema["allOf"]):
        return False
    if "anyOf" in schema and not any(is_schema_valid(instance, child, root) for child in schema["anyOf"]):
        return False
    if "oneOf" in schema and sum(is_schema_valid(instance, child, root) for child in schema["oneOf"]) != 1:
        return False
    if "not" in schema and is_schema_valid(instance, schema["not"], root):
        return False
    if "if" in schema:
        branch = "then" if is_schema_valid(instance, schema["if"], root) else "else"
        if branch in schema and not is_schema_valid(instance, schema[branch], root):
            return False
    if "const" in schema and not json_equal(instance, schema["const"]):
        return False
    if "enum" in schema and not any(json_equal(instance, item) for item in schema["enum"]):
        return False

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = expected_type if isinstance(expected_type, list) else [expected_type]
        type_matches = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "integer": lambda value: type(value) is int,
            "number": lambda value: type(value) in (int, float),
            "boolean": lambda value: isinstance(value, bool),
            "null": lambda value: value is None,
        }
        if not any(type_matches[name](instance) for name in allowed_types):
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
            encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in instance]
            if len(encoded) != len(set(encoded)):
                return False
        if "items" in schema and not all(is_schema_valid(item, schema["items"], root) for item in instance):
            return False
        if "contains" in schema:
            match_count = sum(is_schema_valid(item, schema["contains"], root) for item in instance)
            if match_count < schema.get("minContains", 1):
                return False
            if "maxContains" in schema and match_count > schema["maxContains"]:
                return False

    if isinstance(instance, dict):
        if any(name not in instance for name in schema.get("required", [])):
            return False
        properties = schema.get("properties", {})
        for name, value in instance.items():
            if name in properties and not is_schema_valid(value, properties[name], root):
                return False
            if name not in properties and schema.get("additionalProperties") is False:
                return False

    return True


def valid_input():
    return {
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


def valid_result():
    summary = {name: 0 for name in SUMMARY_FIELDS}
    summary["node_decision_count"] = 1
    summary["ready_node_count"] = 1
    return {
        "schema_id": "urn:sagekit:ready-resolution:v1:result",
        "schema_version": 1,
        "graph_digest": "a" * 64,
        "graph_generation": 1,
        "input_digest": "b" * 64,
        "graph_disposition": "READY",
        "node_decisions": [
            {
                "node_id": "阶段/节点 α",
                "disposition": "READY",
                "reason_codes": ["DEPENDENCIES_SATISFIED"],
                "blocking_node_ids": [],
                "blocking_resource_ids": [],
                "blocking_refs": [],
            }
        ],
        "join_decisions": [],
        "summary": summary,
    }


def valid_error():
    return {
        "schema_id": "urn:sagekit:ready-resolution:v1:error",
        "schema_version": 1,
        "error_code": "REQUIRED_INPUT_INVALID",
        "issues": [
            {
                "path": "$.node_states[0].status",
                "code": "VALUE_NOT_ALLOWED",
            }
        ],
    }


class ReadyResolutionContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = {name: CANONICAL / name for name in RESOURCE_NAMES}
        cls.packaged = {name: PACKAGED / name for name in RESOURCE_NAMES}
        missing = [
            str(path.relative_to(REPOSITORY)).replace("\\", "/")
            for name, path in (*cls.canonical.items(), *cls.packaged.items())
            if name != "error.schema.json"
            if not path.is_file()
        ]
        if missing:
            raise AssertionError(
                "Stage 4A native TDD RED: the six contract resources do not exist: "
                + ", ".join(missing)
            )
        cls.manifest = load_json(cls.canonical["contract.json"])
        cls.graph_schema = load_json(GRAPH_SCHEMA)
        cls.input_schema = load_json(cls.canonical["input.schema.json"])
        cls.result_schema = load_json(cls.canonical["result.schema.json"])
        cls.error_schema = (
            load_json(cls.canonical["error.schema.json"])
            if cls.canonical["error.schema.json"].is_file()
            else None
        )

    def test_node_dependency_blockers_align_with_graph_cardinality(self):
        blocking_node_ids = self.result_schema["$defs"]["node_decision"]["properties"]["blocking_node_ids"]
        self.assertEqual(10000, blocking_node_ids["maxItems"])

    def test_node_resource_blockers_align_with_graph_cardinality(self):
        blocking_resource_ids = self.result_schema["$defs"]["node_decision"]["properties"][
            "blocking_resource_ids"
        ]
        self.assertEqual(10000, blocking_resource_ids["maxItems"])

    def test_join_node_blockers_align_with_graph_cardinality(self):
        blocking_node_ids = self.result_schema["$defs"]["join_decision"]["properties"]["blocking_node_ids"]
        self.assertEqual(10000, blocking_node_ids["maxItems"])

    def test_rejected_authority_and_evidence_refs_fit_without_truncation(self):
        for decision in ("node_decision", "join_decision"):
            with self.subTest(decision=decision):
                blocking_refs = self.result_schema["$defs"][decision]["properties"]["blocking_refs"]
                self.assertEqual(101, blocking_refs["maxItems"])

    def test_error_contract_includes_graph_too_large(self):
        self.assertIn("GRAPH_TOO_LARGE", self.error_schema["properties"]["error_code"]["enum"])

    def test_error_contract_includes_resolution_limit_exceeded(self):
        self.assertIn(
            "RESOLUTION_LIMIT_EXCEEDED",
            self.error_schema["properties"]["error_code"]["enum"],
        )

    def test_contract_declares_resolver_graph_admission_bounds(self):
        self.assertEqual(
            {
                "max_graph_canonical_bytes": 8388608,
                "max_graph_nodes": 10000,
                "max_graph_joins": 10000,
                "max_node_dependencies": 10000,
                "max_node_resources": 10000,
                "max_join_requires": 10000,
                "max_blocking_node_ids": 10000,
                "max_blocking_resource_ids": 10000,
                "max_blocking_refs": 101,
            },
            self.manifest["resolver_admission_bounds"],
        )

    def test_blocker_boundaries_are_expressible_without_truncation(self):
        opaque_ids = [f"阻塞/节点/{index}" for index in range(10000)]

        node_result = valid_result()
        node_result["node_decisions"][0].update(
            disposition="BLOCKED",
            reason_codes=["DEPENDENCY_FAILED"],
            blocking_node_ids=opaque_ids[:101],
        )
        self.assertTrue(is_schema_valid(node_result, self.result_schema))
        node_result["node_decisions"][0]["blocking_node_ids"] = opaque_ids
        self.assertTrue(is_schema_valid(node_result, self.result_schema))
        node_result["node_decisions"][0]["blocking_node_ids"] = opaque_ids + ["boundary-plus-one"]
        self.assertFalse(is_schema_valid(node_result, self.result_schema))
        dependency_overflow = minimal_graph(
            nodes=[
                minimal_node(
                    depends_on=opaque_ids + ["boundary-plus-one"],
                )
            ]
        )
        self.assertEqual(
            "RESOLUTION_LIMIT_EXCEEDED",
            reference_graph_admission_error(
                dependency_overflow,
                0,
                self.manifest["resolver_admission_bounds"],
            ),
        )

        resource_result = valid_result()
        resource_result["node_decisions"][0].update(
            disposition="WAITING_RESOURCE",
            reason_codes=["RESOURCE_UNKNOWN"],
            blocking_resource_ids=[f"resource\\path-looking\\{index}" for index in range(10000)],
        )
        self.assertTrue(is_schema_valid(resource_result, self.result_schema))
        resource_result["node_decisions"][0]["blocking_resource_ids"].append("resource-boundary-plus-one")
        self.assertFalse(is_schema_valid(resource_result, self.result_schema))

        join_result = valid_result()
        join_result["join_decisions"] = [
            {
                "join_id": "汇合/边界",
                "disposition": "BLOCKED",
                "reason_codes": ["JOIN_NODE_FAILED"],
                "blocking_node_ids": opaque_ids,
                "blocking_refs": [],
            }
        ]
        join_result["summary"]["join_decision_count"] = 1
        join_result["summary"]["blocked_join_count"] = 1
        join_result["graph_disposition"] = "BLOCKED"
        self.assertTrue(is_schema_valid(join_result, self.result_schema))
        join_result["join_decisions"][0]["blocking_node_ids"] = opaque_ids + ["join-boundary-plus-one"]
        self.assertFalse(is_schema_valid(join_result, self.result_schema))

    def test_rejected_reference_union_preserves_authority_evidence_and_digest(self):
        evidence_refs = [f"evidence/rejected/{index}" for index in range(100)]
        authority_ref = "authority/distinct-review"
        decision_input = valid_input()
        decision_input["external_join_decisions"][0].update(
            decision="REJECTED",
            authority_ref=authority_ref,
            evidence_refs=evidence_refs,
        )
        digest_before = semantic_input_digest(decision_input, self.input_schema)
        union = rejected_blocking_refs(authority_ref, evidence_refs)
        self.assertEqual(101, len(union))
        self.assertEqual({authority_ref, *evidence_refs}, set(union))
        self.assertEqual(digest_before, semantic_input_digest(decision_input, self.input_schema))

        rejected_result = valid_result()
        rejected_result["join_decisions"] = [
            {
                "join_id": "manual-review",
                "disposition": "REJECTED",
                "reason_codes": ["EXTERNAL_DECISION_REJECTED"],
                "blocking_node_ids": [],
                "blocking_refs": union,
            }
        ]
        rejected_result["summary"]["join_decision_count"] = 1
        rejected_result["summary"]["rejected_join_count"] = 1
        rejected_result["graph_disposition"] = "BLOCKED"
        self.assertTrue(is_schema_valid(rejected_result, self.result_schema))
        rejected_result["join_decisions"][0]["blocking_refs"] = union + ["evidence/overflow"]
        self.assertFalse(is_schema_valid(rejected_result, self.result_schema))

        duplicate_input = copy.deepcopy(decision_input)
        duplicate_input["external_join_decisions"][0]["authority_ref"] = evidence_refs[0]
        duplicate_digest = semantic_input_digest(duplicate_input, self.input_schema)
        duplicate_union = rejected_blocking_refs(evidence_refs[0], evidence_refs)
        self.assertEqual(100, len(duplicate_union))
        self.assertEqual(set(evidence_refs), set(duplicate_union))
        self.assertEqual(duplicate_digest, semantic_input_digest(duplicate_input, self.input_schema))
        self.assertEqual(evidence_refs, duplicate_input["external_join_decisions"][0]["evidence_refs"])

    def test_graph_canonical_byte_admission_is_inclusive_and_uses_strict_json(self):
        bounds = self.manifest["resolver_admission_bounds"]
        graph = minimal_graph(graph_id="")
        overhead = len(canonical_json_bytes(graph))
        graph["graph_id"] = "图" + ("x" * (bounds["max_graph_canonical_bytes"] - overhead - 3))
        exact_bytes = canonical_json_bytes(graph)
        self.assertEqual(bounds["max_graph_canonical_bytes"], len(exact_bytes))
        self.assertTrue(is_schema_valid(graph, self.graph_schema))
        self.assertIsNone(reference_graph_admission_error(graph, len(exact_bytes), bounds))

        graph["graph_id"] += "x"
        over_bytes = canonical_json_bytes(graph)
        self.assertEqual(bounds["max_graph_canonical_bytes"] + 1, len(over_bytes))
        self.assertTrue(is_schema_valid(graph, self.graph_schema))
        self.assertEqual(
            "GRAPH_TOO_LARGE",
            reference_graph_admission_error(graph, len(over_bytes), bounds),
        )

    def test_graph_structural_admission_boundaries_are_inclusive(self):
        bounds = self.manifest["resolver_admission_bounds"]

        node_boundary = minimal_graph(
            nodes=[minimal_node(f"node-{index}") for index in range(10000)]
        )
        self.assertTrue(is_schema_valid(node_boundary, self.graph_schema))
        self.assertIsNone(reference_graph_admission_error(node_boundary, 0, bounds))
        node_boundary["nodes"].append(minimal_node("node-10000"))
        self.assertTrue(is_schema_valid(node_boundary, self.graph_schema))
        self.assertEqual(
            "RESOLUTION_LIMIT_EXCEEDED",
            reference_graph_admission_error(node_boundary, 0, bounds),
        )

        join_boundary = minimal_graph(
            joins=[
                {"id": f"join-{index}", "requires": ["node-0"], "policy": "all-required"}
                for index in range(10000)
            ]
        )
        self.assertTrue(is_schema_valid(join_boundary, self.graph_schema))
        self.assertIsNone(reference_graph_admission_error(join_boundary, 0, bounds))
        join_boundary["joins"].append(
            {"id": "join-10000", "requires": ["node-0"], "policy": "all-required"}
        )
        self.assertTrue(is_schema_valid(join_boundary, self.graph_schema))
        self.assertEqual(
            "RESOLUTION_LIMIT_EXCEEDED",
            reference_graph_admission_error(join_boundary, 0, bounds),
        )

        for field, bound_name in (
            ("depends_on", "max_node_dependencies"),
            ("resources", "max_node_resources"),
        ):
            with self.subTest(field=field):
                values = [f"{field}/opaque/{index}" for index in range(bounds[bound_name])]
                graph = minimal_graph(nodes=[minimal_node(**{field: values})])
                self.assertTrue(is_schema_valid(graph, self.graph_schema))
                self.assertIsNone(reference_graph_admission_error(graph, 0, bounds))
                values.append(f"{field}/boundary-plus-one")
                self.assertTrue(is_schema_valid(graph, self.graph_schema))
                self.assertEqual(
                    "RESOLUTION_LIMIT_EXCEEDED",
                    reference_graph_admission_error(graph, 0, bounds),
                )

        requires = [f"node-reference/{index}" for index in range(bounds["max_join_requires"])]
        requires_graph = minimal_graph(
            joins=[{"id": "join-limit", "requires": requires, "policy": "all-required"}]
        )
        self.assertTrue(is_schema_valid(requires_graph, self.graph_schema))
        self.assertIsNone(reference_graph_admission_error(requires_graph, 0, bounds))
        requires.append("node-reference/boundary-plus-one")
        self.assertTrue(is_schema_valid(requires_graph, self.graph_schema))
        self.assertEqual(
            "RESOLUTION_LIMIT_EXCEEDED",
            reference_graph_admission_error(requires_graph, 0, bounds),
        )

    def test_graph_contract_blobs_and_unbounded_domains_are_unchanged(self):
        for relative_path, expected_blob in PROTECTED_GIT_BLOBS.items():
            actual_blob = subprocess.run(
                ["git", "hash-object", relative_path],
                cwd=REPOSITORY,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            self.assertEqual(expected_blob, actual_blob, relative_path)
        self.assertNotIn("maxItems", self.graph_schema["properties"]["nodes"])
        self.assertNotIn("maxItems", self.graph_schema["properties"]["joins"])
        self.assertNotIn("maxItems", self.graph_schema["$defs"]["node"]["properties"]["depends_on"])
        self.assertNotIn("maxItems", self.graph_schema["$defs"]["node"]["properties"]["resources"])
        self.assertNotIn("maxItems", self.graph_schema["$defs"]["join"]["properties"]["requires"])

    def test_admission_error_mapping_is_exact_and_not_graph_validation(self):
        semantics = self.manifest["error_semantics"]
        self.assertEqual(ERROR_CODES, set(self.error_schema["properties"]["error_code"]["enum"]))
        self.assertIn("max_graph_canonical_bytes", semantics["GRAPH_TOO_LARGE"])
        self.assertIn("not GRAPH_INVALID", semantics["RESOLUTION_LIMIT_EXCEEDED"])
        self.assertIn("max_input_canonical_bytes", semantics["INPUT_TOO_LARGE"])
        self.assertIn("max_result_canonical_bytes", semantics["RESULT_TOO_LARGE"])
        text = json.dumps(
            {
                "admission": self.manifest["resolver_admission_semantics"],
                "boundaries": self.manifest["semantic_boundaries"],
                "error": self.error_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for phrase in (
            "optional ready resolver invocation",
            "measures only the ready resolution input instance",
            "does not include the separately supplied graph argument",
            "independently admitted by max_graph_canonical_bytes",
            "do not change graph contract v1 validity",
            "do not change the graph semantic digest",
            "another host or runtime",
            "exactly at a bound is admitted",
            "boundary plus one is rejected",
            "never rewrites, truncates, or partially processes",
            "not graph_invalid",
            "no partial result",
            "contains no node or join decisions",
        ):
            self.assertIn(phrase, text)

    def test_exact_blocker_preservation_forbids_false_success_patterns(self):
        text = json.dumps(
            {
                "contract": self.manifest,
                "result": self.result_schema,
                "error": self.error_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for phrase in (
            "every applicable blocking",
            "emitted completely and exactly",
            "truncated at 100 or 10000",
            "silently omitted",
            "first n plus truncated=true",
            "hash or digest",
            "opaque blocker identities remain unchanged",
            "unique union of authority_ref",
            "never mutates the validated authority/evidence input",
            "whole resolution returns resolution_limit_exceeded",
            "whole resolution returns result_too_large",
            "error never masquerades as resolution success",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("truncated", property_names((self.result_schema, self.error_schema)))
        self.assertIn(
            "stage 4b resolver implementation remains deferred",
            self.manifest["compatibility"].lower(),
        )

    def test_eight_resources_parse_and_use_stable_identities(self):
        self.assertTrue(
            self.canonical["error.schema.json"].is_file(),
            "Stage 4A-C3 TDD RED: canonical error.schema.json does not exist",
        )
        self.assertTrue(
            self.packaged["error.schema.json"].is_file(),
            "Stage 4A-C3 TDD RED: packaged error.schema.json does not exist",
        )
        for path in (*self.canonical.values(), *self.packaged.values()):
            load_json(path)
        self.assertEqual("urn:sagekit:ready-resolution:v1", self.manifest["contract_id"])
        self.assertEqual("urn:sagekit:ready-resolution:v1:input", self.input_schema["$id"])
        self.assertEqual("urn:sagekit:ready-resolution:v1:result", self.result_schema["$id"])
        self.assertEqual("urn:sagekit:ready-resolution:v1:error", self.error_schema["$id"])
        self.assertEqual(1, self.input_schema["properties"]["schema_version"]["const"])
        self.assertEqual(1, self.result_schema["properties"]["schema_version"]["const"])
        self.assertEqual(1, self.error_schema["properties"]["schema_version"]["const"])

    def test_canonical_and_packaged_families_are_exact_byte_mirrors(self):
        self.assertEqual(RESOURCE_NAMES, tuple(sorted(path.name for path in CANONICAL.iterdir())))
        self.assertEqual(RESOURCE_NAMES, tuple(sorted(path.name for path in PACKAGED.iterdir())))
        for name in RESOURCE_NAMES:
            self.assertEqual(self.canonical[name].read_bytes(), self.packaged[name].read_bytes())

    def test_manifest_binds_canonical_schema_bytes(self):
        self.assertEqual("sagekit-ready-resolution-contract", self.manifest["contract_family"])
        self.assertEqual("v1", self.manifest["version"])
        self.assertEqual(1, self.manifest["manifest_version"])
        resources = self.manifest["resources"]
        self.assertEqual({"input_schema", "result_schema", "error_schema"}, set(resources))
        for key, name in (
            ("input_schema", "input.schema.json"),
            ("result_schema", "result.schema.json"),
            ("error_schema", "error.schema.json"),
        ):
            self.assertEqual(name, resources[key]["resource"])
            self.assertEqual(canonical_sha256(self.canonical[name]), resources[key]["canonical_sha256"])
            self.assertRegex(resources[key]["canonical_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual("sagekit/resources/contracts/ready-resolution/v1", self.manifest["packaged_mirror"]["path"])
        self.assertIn("byte-identical", self.manifest["packaged_mirror"]["expectation"])
        digest_semantics = self.manifest["digest_semantics"].lower()
        self.assertIn("canonical resource", digest_semantics)
        self.assertIn("resource integrity", digest_semantics)
        self.assertIn("not execution identity", digest_semantics)

    def test_manifest_binds_graph_node_result_and_runtime_dependencies(self):
        for relative_path, expected in DEPENDENCY_DIGESTS.items():
            self.assertEqual(expected, canonical_sha256(REPOSITORY / relative_path), relative_path)
        dependencies = self.manifest["dependencies"]
        self.assertEqual(
            {
                "graph_contract_v1",
                "node_result_v1",
                "runtime_state_contract_v1",
            },
            set(dependencies),
        )
        graph = dependencies["graph_contract_v1"]
        self.assertEqual("urn:sagekit:graph-contract:v1", graph["contract_id"])
        self.assertEqual(DEPENDENCY_DIGESTS["docs/contracts/graph/v1/contract.json"], graph["canonical_contract_sha256"])
        self.assertEqual(
            DEPENDENCY_DIGESTS["docs/contracts/graph/v1/graph.schema.json"],
            graph["canonical_resource_integrity"]["graph_schema_sha256"],
        )
        node_result = dependencies["node_result_v1"]
        self.assertEqual("urn:sagekit:graph-contract:v1:node-result", node_result["schema_id"])
        self.assertEqual(
            DEPENDENCY_DIGESTS["docs/contracts/graph/v1/node-result.schema.json"],
            node_result["canonical_schema_sha256"],
        )
        runtime = dependencies["runtime_state_contract_v1"]
        self.assertEqual("urn:sagekit:runtime-state-contract:v1", runtime["contract_id"])
        self.assertEqual(
            DEPENDENCY_DIGESTS["docs/contracts/runtime-state/v1/contract.json"],
            runtime["canonical_contract_sha256"],
        )
        self.assertEqual(
            {
                "state_schema_sha256": DEPENDENCY_DIGESTS["docs/contracts/runtime-state/v1/state.schema.json"],
                "event_schema_sha256": DEPENDENCY_DIGESTS["docs/contracts/runtime-state/v1/event.schema.json"],
            },
            runtime["canonical_resource_integrity"],
        )

    def test_contract_defines_domain_separated_semantic_input_digest(self):
        digest_contract = self.manifest["semantic_input_digest"]
        self.assertEqual("SHA-256", digest_contract["algorithm"])
        self.assertEqual("sagekit-ready-resolution-input-v1\u0000", digest_contract["domain_separator"])
        self.assertEqual(INPUT_DIGEST_DOMAIN.hex(), digest_contract["domain_separator_utf8_hex"])
        self.assertEqual(
            "70133af3c18e621a9f4586e43b8fe1807b5a0c85e4976eea302745ec1a8b0a37",
            semantic_input_digest(valid_input(), self.input_schema),
        )
        text = json.dumps(digest_contract, ensure_ascii=False, sort_keys=True).lower()
        for phrase in (
            "strict validation",
            "duplicate",
            "unknown",
            "canonical normalized input bytes",
            "unicode code point",
            "node_states",
            "node_id",
            "resource_availability",
            "resource_id",
            "external_join_decisions",
            "join_id",
            "evidence_refs",
            "opaque",
            "not authority",
            "separate from graph semantic digest",
        ):
            self.assertIn(phrase, text)

    def test_semantic_input_digest_is_order_independent_for_identity_arrays_and_evidence(self):
        candidate = valid_input()
        candidate["node_states"].append(
            {
                "node_id": "another-node",
                "status": "NO_ACTION_REQUIRED",
                "result_digest": "node-result:sha256:" + "c" * 64,
                "evidence_refs": ["evidence/z", "evidence/a"],
            }
        )
        candidate["resource_availability"].append(
            {
                "resource_id": "gpu.heavy",
                "availability": "UNKNOWN",
                "reason_code": "RESOURCE_UNKNOWN",
                "evidence_refs": ["evidence/z", "evidence/a"],
            }
        )
        candidate["external_join_decisions"].append(
            {
                "join_id": "corrective-review",
                "decision": "REJECTED",
                "authority_ref": "authority/corrective-rejection",
                "evidence_refs": ["evidence/z", "evidence/a"],
            }
        )
        reordered = copy.deepcopy(candidate)
        for name in ("node_states", "resource_availability", "external_join_decisions"):
            reordered[name].reverse()
            for item in reordered[name]:
                if "evidence_refs" in item:
                    item["evidence_refs"].reverse()
        self.assertEqual(
            semantic_input_digest(candidate, self.input_schema),
            semantic_input_digest(reordered, self.input_schema),
        )

    def test_semantic_input_digest_binds_every_decision_input(self):
        original = valid_input()
        expected = semantic_input_digest(original, self.input_schema)
        mutations = []

        changed = copy.deepcopy(original)
        changed["node_states"][0]["status"] = "RUNNING"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["resource_availability"][0].update(
            availability="AVAILABLE", reason_code="RESOURCE_AVAILABLE"
        )
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["resource_availability"][0]["evidence_refs"] = ["evidence/other-resource"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["external_join_decisions"][0]["decision"] = "REJECTED"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["external_join_decisions"][0]["authority_ref"] = "authority/other"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["external_join_decisions"][0]["evidence_refs"] = ["evidence/other"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["node_states"][0]["evidence_refs"] = ["evidence/node"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["graph_digest"] = "d" * 64
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["graph_generation"] = 2
        mutations.append(changed)

        for candidate in mutations:
            self.assertNotEqual(expected, semantic_input_digest(candidate, self.input_schema))

        terminal = copy.deepcopy(original)
        terminal["node_states"][0].update(
            status="SUCCEEDED",
            result_digest="node-result:sha256:" + "c" * 64,
        )
        changed_digest = copy.deepcopy(terminal)
        changed_digest["node_states"][0]["result_digest"] = "node-result:sha256:" + "d" * 64
        self.assertNotEqual(
            semantic_input_digest(terminal, self.input_schema),
            semantic_input_digest(changed_digest, self.input_schema),
        )

    def test_semantic_input_digest_preserves_opaque_ids_and_rejects_before_digest(self):
        candidate = valid_input()
        candidate["node_states"][0]["node_id"] = " C:\\Looks\\Like\\Path/阶段/ß "
        candidate["resource_availability"][0]["resource_id"] = "../资源/CPU"
        candidate["external_join_decisions"][0]["join_id"] = "JOIN/İ/α"
        preserved = copy.deepcopy(candidate)
        preserved_digest = semantic_input_digest(candidate, self.input_schema)
        self.assertEqual(preserved, candidate)
        trimmed = copy.deepcopy(candidate)
        trimmed["node_states"][0]["node_id"] = trimmed["node_states"][0]["node_id"].strip()
        self.assertNotEqual(
            preserved_digest,
            semantic_input_digest(trimmed, self.input_schema),
        )

        for array_name, identity_name in (
            ("node_states", "node_id"),
            ("resource_availability", "resource_id"),
            ("external_join_decisions", "join_id"),
        ):
            duplicate = valid_input()
            second = copy.deepcopy(duplicate[array_name][0])
            if array_name == "node_states":
                second["status"] = "RUNNING"
            elif array_name == "resource_availability":
                second.update(availability="UNKNOWN", reason_code="RESOURCE_UNKNOWN")
            else:
                second["authority_ref"] = "authority/conflict"
            duplicate[array_name].append(second)
            with self.assertRaises(ValueError, msg=identity_name):
                semantic_input_digest(duplicate, self.input_schema)
        extra = valid_input()
        extra["unknown"] = True
        with self.assertRaises(ValueError):
            semantic_input_digest(extra, self.input_schema)

    def test_result_is_bound_to_input_digest_and_cannot_be_reused_by_graph_only(self):
        self.assertIn("input_digest", self.result_schema["required"])
        self.assertFalse(
            is_schema_valid(
                {key: value for key, value in valid_result().items() if key != "input_digest"},
                self.result_schema,
            )
        )
        text = json.dumps(
            {
                "manifest": self.manifest,
                "result": self.result_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for phrase in (
            "matching input_digest",
            "input_digest mismatch",
            "must not reuse",
            "graph_digest alone",
            "external_join_decision",
            "authority",
            "evidence",
            "available",
            "busy",
            "unavailable",
            "unknown",
        ):
            self.assertIn(phrase, text)

    def test_error_is_a_bounded_mutually_exclusive_output_not_partial_result(self):
        self.assertTrue(is_schema_valid(valid_error(), self.error_schema))
        self.assertFalse(is_schema_valid(valid_error(), self.result_schema))
        self.assertFalse(is_schema_valid(valid_result(), self.error_schema))
        forbidden = {
            "node_decisions",
            "join_decisions",
            "graph_disposition",
            "summary",
            "ready_nodes",
        }
        self.assertTrue(forbidden.isdisjoint(property_names(self.error_schema)))
        for name in forbidden:
            candidate = valid_error()
            candidate[name] = []
            self.assertFalse(is_schema_valid(candidate, self.error_schema), name)
        text = json.dumps(
            {
                "manifest": self.manifest,
                "error": self.error_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for phrase in (
            "mutually exclusive",
            "invalid required input",
            "not a partial result",
            "must not generate",
            "partial",
            "graph_invalid",
            "graph_binding_mismatch",
            "input_too_large",
            "graph_too_large",
            "resolution_limit_exceeded",
            "result_too_large",
            "not runtime mutation",
            "not a blocked node",
            "handoff",
            "acceptance",
        ):
            self.assertIn(phrase, text)

    def test_error_issues_are_deterministic_unique_and_bounded(self):
        issues = self.error_schema["properties"]["issues"]
        self.assertEqual(1, issues["minItems"])
        self.assertEqual(100, issues["maxItems"])
        self.assertTrue(issues["uniqueItems"])
        issue = self.error_schema["$defs"]["issue"]
        self.assertEqual({"path", "code"}, set(issue["required"]))
        self.assertEqual({"path", "code"}, set(issue["properties"]))
        self.assertEqual(1024, issue["properties"]["path"]["maxLength"])
        self.assertRegex("VALUE_NOT_ALLOWED", issue["properties"]["code"]["pattern"])
        self.assertNotRegex("not-stable", issue["properties"]["code"]["pattern"])
        self.assertFalse(
            is_schema_valid(
                {
                    **valid_error(),
                    "issues": [valid_error()["issues"][0]] * 2,
                },
                self.error_schema,
            )
        )
        description = issues["description"].lower()
        for phrase in (
            "deterministic",
            "path",
            "code",
            "stop",
            "100",
            "no traceback",
            "no payload",
        ):
            self.assertIn(phrase, description)

    def test_invalid_input_error_cannot_claim_input_digest(self):
        invalid = valid_error()
        invalid["input_digest"] = "c" * 64
        self.assertFalse(is_schema_valid(invalid, self.error_schema))

        post_validation = valid_error()
        post_validation["error_code"] = "GRAPH_BINDING_MISMATCH"
        post_validation["graph_digest"] = "a" * 64
        post_validation["graph_generation"] = 1
        post_validation["input_digest"] = "c" * 64
        self.assertTrue(is_schema_valid(post_validation, self.error_schema))

    def test_input_and_result_required_fields_are_exact(self):
        self.assertEqual(
            {
                "schema_id",
                "schema_version",
                "graph_digest",
                "graph_generation",
                "node_states",
                "resource_availability",
                "external_join_decisions",
            },
            set(self.input_schema["required"]),
        )
        self.assertEqual(
            {
                "node_id",
                "status",
                "evidence_refs",
            },
            set(self.input_schema["$defs"]["node_state"]["required"]),
        )
        self.assertEqual(
            {"resource_id", "availability", "reason_code", "evidence_refs"},
            set(self.input_schema["$defs"]["resource_snapshot"]["required"]),
        )
        self.assertEqual(
            {"join_id", "decision"},
            set(self.input_schema["$defs"]["external_join_decision"]["required"]),
        )
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
            set(self.result_schema["required"]),
        )
        self.assertEqual(
            {"schema_id", "schema_version", "error_code", "issues"},
            set(self.error_schema["required"]),
        )
        self.assertEqual(
            {
                "node_id",
                "disposition",
                "reason_codes",
                "blocking_node_ids",
                "blocking_resource_ids",
                "blocking_refs",
            },
            set(self.result_schema["$defs"]["node_decision"]["required"]),
        )
        self.assertEqual(
            {"join_id", "disposition", "reason_codes", "blocking_node_ids", "blocking_refs"},
            set(self.result_schema["$defs"]["join_decision"]["required"]),
        )
        self.assertEqual(SUMMARY_FIELDS, set(self.result_schema["$defs"]["summary"]["required"]))

    def test_all_enums_are_explicit_and_stable(self):
        self.assertEqual(NODE_STATUSES, set(self.input_schema["$defs"]["node_state"]["properties"]["status"]["enum"]))
        self.assertEqual(
            RESOURCE_AVAILABILITY,
            set(self.input_schema["$defs"]["resource_snapshot"]["properties"]["availability"]["enum"]),
        )
        self.assertEqual(
            EXTERNAL_DECISIONS,
            set(self.input_schema["$defs"]["external_join_decision"]["properties"]["decision"]["enum"]),
        )
        self.assertEqual(
            NODE_DISPOSITIONS,
            set(self.result_schema["$defs"]["node_decision"]["properties"]["disposition"]["enum"]),
        )
        self.assertEqual(
            JOIN_DISPOSITIONS,
            set(self.result_schema["$defs"]["join_decision"]["properties"]["disposition"]["enum"]),
        )
        self.assertEqual(GRAPH_DISPOSITIONS, set(self.result_schema["properties"]["graph_disposition"]["enum"]))
        self.assertEqual(ERROR_CODES, set(self.error_schema["properties"]["error_code"]["enum"]))
        reason_codes = set(self.result_schema["$defs"]["reason_code"]["enum"])
        self.assertTrue(REQUIRED_REASON_CODES.issubset(reason_codes))
        self.assertNotIn("REQUIRED_INPUT_INVALID", reason_codes)

    def test_every_object_is_closed_and_every_array_is_bounded(self):
        for name, schema in (
            ("input", self.input_schema),
            ("result", self.result_schema),
            ("error", self.error_schema),
        ):
            objects = list(object_schemas(schema))
            self.assertTrue(objects, name)
            for object_schema in objects:
                self.assertIs(False, object_schema.get("additionalProperties"), object_schema)
            arrays = [
                item
                for item in walk(schema)
                if isinstance(item, dict) and item.get("type") == "array"
            ]
            self.assertTrue(arrays, name)
            for array_schema in arrays:
                self.assertIn("maxItems", array_schema, array_schema)

    def test_graph_derived_ids_remain_opaque_unicode_and_slash_strings(self):
        node_id = self.input_schema["$defs"]["node_id"]
        for identity_schema in (
            node_id,
            self.input_schema["$defs"]["graph_id"],
            self.result_schema["$defs"]["node_id"],
            self.result_schema["$defs"]["graph_id"],
        ):
            self.assertEqual("string", identity_schema["type"])
            self.assertEqual(1, identity_schema["minLength"])
            self.assertNotIn("maxLength", identity_schema)
            self.assertNotIn("pattern", identity_schema)
        for value in ("阶段/节点 α", r"lane\worker", " node with spaces ", "!leading", "節" * 300):
            candidate = valid_input()
            candidate["node_states"][0]["node_id"] = value
            candidate["resource_availability"][0]["resource_id"] = value
            candidate["external_join_decisions"][0]["join_id"] = value
            self.assertTrue(is_schema_valid(candidate, self.input_schema), value)
            result = valid_result()
            result["join_decisions"] = [
                {
                    "join_id": value,
                    "disposition": "SATISFIED",
                    "reason_codes": ["JOIN_SATISFIED"],
                    "blocking_node_ids": [],
                    "blocking_refs": [],
                }
            ]
            result["summary"]["join_decision_count"] = 1
            result["summary"]["satisfied_join_count"] = 1
            self.assertTrue(is_schema_valid(result, self.result_schema), value)
        candidate = valid_input()
        candidate["node_states"][0]["node_id"] = ""
        self.assertFalse(is_schema_valid(candidate, self.input_schema))
        candidate = valid_input()
        candidate["resource_availability"][0]["resource_id"] = ""
        self.assertFalse(is_schema_valid(candidate, self.input_schema))
        candidate = valid_input()
        candidate["external_join_decisions"][0]["join_id"] = ""
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

    def test_result_separates_opaque_blocking_identities_from_references(self):
        node_properties = self.result_schema["$defs"]["node_decision"]["properties"]
        join_properties = self.result_schema["$defs"]["join_decision"]["properties"]
        self.assertEqual({"$ref": "#/$defs/node_id"}, node_properties["blocking_node_ids"]["items"])
        self.assertEqual({"$ref": "#/$defs/graph_id"}, node_properties["blocking_resource_ids"]["items"])
        self.assertEqual({"$ref": "#/$defs/node_id"}, join_properties["blocking_node_ids"]["items"])
        self.assertNotIn("blocking_ids", node_properties)
        self.assertNotIn("blocking_ids", join_properties)

        identity_cases = (
            ("blocking_node_ids", "/absolute-looking-node"),
            ("blocking_resource_ids", r"C:\looking\resource"),
            ("blocking_node_ids", "阻塞/节点 δ"),
            ("blocking_node_ids", "opaque-" + ("節" * 1100)),
        )
        for field, identity in identity_cases:
            result = valid_result()
            decision = result["node_decisions"][0]
            decision.update(
                disposition="BLOCKED",
                reason_codes=["NODE_BLOCKED"],
                blocking_node_ids=[],
                blocking_resource_ids=[],
            )
            decision[field] = [identity]
            self.assertTrue(is_schema_valid(result, self.result_schema), (field, identity))

        for reference in (
            "/absolute-looking-node",
            r"C:\looking\resource",
            "opaque-" + ("節" * 1100),
        ):
            result = valid_result()
            result["node_decisions"][0].update(
                blocking_node_ids=[],
                blocking_resource_ids=[],
                blocking_refs=[reference],
            )
            self.assertFalse(is_schema_valid(result, self.result_schema), reference)

    def test_result_identity_conditionals_prevent_false_green(self):
        default_reason_codes = {
            "READY": ("DEPENDENCIES_SATISFIED",),
            "WAITING_DEPENDENCY": ("DEPENDENCY_PENDING",),
            "WAITING_RESOURCE": ("RESOURCE_BUSY",),
            "IN_PROGRESS": ("NODE_RUNNING",),
            "NEEDS_CORRECTION": ("NODE_NEEDS_CORRECTION",),
            "HANDOFF_REQUIRED": ("NODE_HANDOFF",),
            "BLOCKED": ("NODE_BLOCKED",),
            "COMPLETED": ("NODE_SUCCEEDED",),
            "CANCELLED": ("NODE_CANCELLED",),
        }

        def node_result(
            disposition,
            node_ids=(),
            resource_ids=(),
            refs=(),
            reason_codes=None,
        ):
            result = valid_result()
            result["node_decisions"][0].update(
                disposition=disposition,
                reason_codes=list(reason_codes or default_reason_codes[disposition]),
                blocking_node_ids=list(node_ids),
                blocking_resource_ids=list(resource_ids),
                blocking_refs=list(refs),
            )
            return result

        self.assertFalse(is_schema_valid(node_result("WAITING_DEPENDENCY"), self.result_schema))
        self.assertTrue(
            is_schema_valid(
                node_result("WAITING_DEPENDENCY", node_ids=("/absolute-looking-node",)),
                self.result_schema,
            )
        )
        self.assertFalse(is_schema_valid(node_result("WAITING_RESOURCE"), self.result_schema))
        self.assertTrue(
            is_schema_valid(
                node_result("WAITING_RESOURCE", resource_ids=(r"C:\looking\resource",)),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(node_result("READY", node_ids=("dependency",)), self.result_schema)
        )
        self.assertFalse(
            is_schema_valid(node_result("READY", resource_ids=("resource",)), self.result_schema)
        )
        self.assertFalse(
            is_schema_valid(node_result("COMPLETED", node_ids=("dependency",)), self.result_schema)
        )
        self.assertFalse(
            is_schema_valid(node_result("COMPLETED", resource_ids=("resource",)), self.result_schema)
        )
        self.assertFalse(
            is_schema_valid(
                node_result("READY", reason_codes=("DEPENDENCY_FAILED",)),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                node_result("COMPLETED", reason_codes=("NODE_HANDOFF",)),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                node_result("READY", refs=("evidence/not-a-blocker",)),
                self.result_schema,
            )
        )
        self.assertTrue(
            is_schema_valid(node_result("BLOCKED", node_ids=("dependency",)), self.result_schema)
        )
        self.assertTrue(
            is_schema_valid(node_result("BLOCKED", refs=("evidence/blocker",)), self.result_schema)
        )

        def join_result(disposition, node_ids=(), refs=(), reason_code="JOIN_SATISFIED"):
            result = valid_result()
            result["join_decisions"] = [
                {
                    "join_id": "join",
                    "disposition": disposition,
                    "reason_codes": [reason_code],
                    "blocking_node_ids": list(node_ids),
                    "blocking_refs": list(refs),
                }
            ]
            return result

        self.assertFalse(is_schema_valid(join_result("WAITING_NODE"), self.result_schema))
        self.assertTrue(
            is_schema_valid(
                join_result(
                    "WAITING_NODE",
                    node_ids=("/absolute-looking-node",),
                    reason_code="JOIN_NODE_PENDING",
                ),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(join_result("SATISFIED", node_ids=("node",)), self.result_schema)
        )
        self.assertFalse(
            is_schema_valid(
                join_result("SATISFIED", reason_code="EXTERNAL_DECISION_MISSING"),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                join_result("SATISFIED", refs=("evidence/not-a-blocker",)),
                self.result_schema,
            )
        )
        self.assertTrue(
            is_schema_valid(
                join_result(
                    "REQUIRES_EXTERNAL_DECISION",
                    reason_code="EXTERNAL_DECISION_MISSING",
                ),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                join_result(
                    "REQUIRES_EXTERNAL_DECISION",
                    node_ids=("fabricated-node",),
                    reason_code="EXTERNAL_DECISION_MISSING",
                ),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                join_result("REJECTED", reason_code="EXTERNAL_DECISION_REJECTED"),
                self.result_schema,
            )
        )
        self.assertTrue(
            is_schema_valid(
                join_result(
                    "REJECTED",
                    refs=("authority/rejection",),
                    reason_code="EXTERNAL_DECISION_REJECTED",
                ),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                join_result(
                    "BLOCKED",
                    refs=("evidence/automatic-failure",),
                    reason_code="JOIN_NODE_FAILED",
                ),
                self.result_schema,
            )
        )
        self.assertTrue(
            is_schema_valid(
                join_result(
                    "BLOCKED",
                    node_ids=("failed-node",),
                    refs=("evidence/automatic-failure",),
                    reason_code="JOIN_NODE_FAILED",
                ),
                self.result_schema,
            )
        )
        self.assertFalse(
            is_schema_valid(
                join_result(
                    "BLOCKED",
                    node_ids=("failed-node",),
                    reason_code="JOIN_SATISFIED",
                ),
                self.result_schema,
            )
        )

    def test_aggregate_canonical_byte_budgets_are_language_neutral_admission_only(self):
        bounds = self.manifest["canonical_byte_budgets"]
        self.assertEqual(16777216, bounds["max_input_canonical_bytes"])
        self.assertEqual(16777216, bounds["max_result_canonical_bytes"])
        self.assertEqual(1048576, bounds["max_error_canonical_bytes"])
        text = json.dumps(
            {
                "bounds": bounds,
                "input": self.input_schema["description"],
                "result": self.result_schema["description"],
                "error": self.error_schema["description"],
                "compatibility": self.manifest["compatibility"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for phrase in (
            "utf-8",
            "object keys lexicographically sorted",
            "no insignificant whitespace",
            "rather than ascii escape",
            "strict json values",
            "admission",
            "not semantic identity or authority",
            "never rewritten or truncated",
            "required_input_invalid",
            "partial or false-success",
            "does not alter the graph digest",
            "does not shrink the graph contract",
            "optional resolver invocation",
            "pre-implementation cardinality corrective",
            "input_too_large",
            "result_too_large",
            "100",
        ):
            self.assertIn(phrase, text)
        measurement = bounds["measurement"].lower()
        for phrase in (
            "without a byte-order mark",
            "unicode code point sequence",
            "duplicate object names",
            "shortest base-10 form",
            "quotation mark",
            "reverse solidus",
            "u+0000 through u+001f",
            "do not escape solidus",
            "non-bmp",
            "unpaired utf-16 surrogate",
            "mandatory json escapes",
        ):
            self.assertIn(phrase, measurement)

        vector = {
            "z": "quote\" reverse\\ control\u0001 astral😀",
            "a": [True, None, 10],
        }
        expected = (
            b'{"a":[true,null,10],"z":"quote\\" reverse\\\\ control\\u0001 astral'
            + "😀".encode("utf-8")
            + b'"}'
        )
        self.assertEqual(expected, canonical_json_bytes(vector))

        boundary_overhead = len(canonical_json_bytes({"id": ""}))
        exact_boundary = {"id": "x" * (bounds["max_input_canonical_bytes"] - boundary_overhead)}
        self.assertEqual(bounds["max_input_canonical_bytes"], len(canonical_json_bytes(exact_boundary)))
        exact_boundary["id"] += "x"
        self.assertEqual(
            bounds["max_input_canonical_bytes"] + 1,
            len(canonical_json_bytes(exact_boundary)),
        )

    def test_corrective_updates_schema_digests_without_changing_dependency_digests(self):
        resources = self.manifest["resources"]
        for key, name in (
            ("input_schema", "input.schema.json"),
            ("result_schema", "result.schema.json"),
            ("error_schema", "error.schema.json"),
        ):
            digest = resources[key]["canonical_sha256"]
            self.assertEqual(canonical_sha256(self.canonical[name]), digest)
            if name == "input.schema.json":
                self.assertEqual(BASELINE_SCHEMA_DIGESTS[name], digest)
            else:
                self.assertNotEqual(BASELINE_SCHEMA_DIGESTS[name], digest)

    def test_node_result_digest_is_conditional_and_no_action_is_evidence_bound(self):
        result_statuses = {
            "SUCCEEDED",
            "NO_ACTION_REQUIRED",
            "FAILED",
            "NEEDS_CORRECTION",
            "DONE_WITH_CONCERNS",
        }
        for status in NODE_STATUSES:
            candidate = valid_input()
            state = candidate["node_states"][0]
            state["status"] = status
            state["evidence_refs"] = ["evidence/node-result"] if status == "NO_ACTION_REQUIRED" else []
            if status in result_statuses:
                self.assertFalse(is_schema_valid(candidate, self.input_schema), status)
                state["result_digest"] = "node-result:sha256:" + "b" * 64
            self.assertTrue(is_schema_valid(candidate, self.input_schema), status)
        candidate = valid_input()
        candidate["node_states"][0].update(
            status="NO_ACTION_REQUIRED",
            result_digest="node-result:sha256:" + "b" * 64,
            evidence_refs=[],
        )
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

    def test_resource_availability_is_explicit_conditional_and_inert(self):
        reason_by_availability = {
            "AVAILABLE": "RESOURCE_AVAILABLE",
            "BUSY": "RESOURCE_BUSY",
            "UNAVAILABLE": "RESOURCE_UNAVAILABLE",
            "UNKNOWN": "RESOURCE_UNKNOWN",
        }
        for availability, reason_code in reason_by_availability.items():
            candidate = valid_input()
            snapshot = candidate["resource_availability"][0]
            snapshot["availability"] = availability
            snapshot["reason_code"] = reason_code
            self.assertTrue(is_schema_valid(candidate, self.input_schema), availability)
            snapshot["reason_code"] = "RESOURCE_UNKNOWN" if reason_code != "RESOURCE_UNKNOWN" else "RESOURCE_BUSY"
            self.assertFalse(is_schema_valid(candidate, self.input_schema), availability)
        candidate = valid_input()
        del candidate["resource_availability"][0]["reason_code"]
        self.assertFalse(is_schema_valid(candidate, self.input_schema))
        description = self.input_schema["$defs"]["resource_snapshot"]["description"].lower()
        for phrase in (
            "host-observed",
            "does not mean lock acquisition",
            "busy maps to waiting_resource",
            "unavailable and unknown remain distinct",
            "missing resources are not available",
            "does not poll, wait for, or acquire",
        ):
            self.assertIn(phrase, description)

    def test_external_join_decisions_fail_closed(self):
        for decision in ("SATISFIED", "REJECTED"):
            candidate = valid_input()
            external = candidate["external_join_decisions"][0]
            external["decision"] = decision
            self.assertTrue(is_schema_valid(candidate, self.input_schema), decision)
            del external["authority_ref"]
            self.assertFalse(is_schema_valid(candidate, self.input_schema), decision)
            external["authority_ref"] = "authority/review-approval"
            external["evidence_refs"] = []
            self.assertFalse(is_schema_valid(candidate, self.input_schema), decision)
        candidate = valid_input()
        candidate["external_join_decisions"][0] = {
            "join_id": "manual-review",
            "decision": "PENDING",
        }
        self.assertTrue(is_schema_valid(candidate, self.input_schema))
        candidate["external_join_decisions"][0]["authority_ref"] = "authority/fake"
        self.assertFalse(is_schema_valid(candidate, self.input_schema))
        description = self.input_schema["$defs"]["external_join_decision"]["description"].lower()
        for phrase in (
            "host-supplied",
            "already-authorized evidence",
            "does not validate human identity",
            "does not open a gate",
            "must not infer satisfied",
            "requires_external_decision",
        ):
            self.assertIn(phrase, description)

    def test_result_decision_shapes_and_bounded_counts_validate(self):
        self.assertTrue(is_schema_valid(valid_result(), self.result_schema))
        result = valid_result()
        result["join_decisions"] = [
            {
                "join_id": "manual-review",
                "disposition": "REQUIRES_EXTERNAL_DECISION",
                "reason_codes": ["EXTERNAL_DECISION_MISSING"],
                "blocking_node_ids": [],
                "blocking_refs": [],
            }
        ]
        result["summary"]["join_decision_count"] = 1
        result["summary"]["requires_external_decision_join_count"] = 1
        result["graph_disposition"] = "WAITING"
        self.assertTrue(is_schema_valid(result, self.result_schema))
        result["summary"]["blocked_node_count"] = -1
        self.assertFalse(is_schema_valid(result, self.result_schema))
        result = valid_result()
        result["node_decisions"][0]["unexpected"] = True
        self.assertFalse(is_schema_valid(result, self.result_schema))

    def test_reason_evidence_and_blocking_boundaries_are_bounded(self):
        for schema in (self.input_schema, self.result_schema):
            for item in walk(schema):
                if not isinstance(item, dict) or item.get("type") != "array":
                    continue
                self.assertIn("maxItems", item)
                if item.get("description") and any(
                    word in item["description"].lower()
                    for word in ("reason", "evidence", "blocking")
                ):
                    self.assertTrue(item.get("uniqueItems"), item)
        result = valid_result()
        reason_limit = self.result_schema["$defs"]["node_decision"]["properties"]["reason_codes"]["maxItems"]
        result["node_decisions"][0]["reason_codes"] = ["NODE_RUNNING"] * (reason_limit + 1)
        self.assertFalse(is_schema_valid(result, self.result_schema))
        candidate = valid_input()
        evidence_limit = self.input_schema["$defs"]["node_state"]["properties"]["evidence_refs"]["maxItems"]
        candidate["node_states"][0]["evidence_refs"] = [
            f"evidence/{index}" for index in range(evidence_limit + 1)
        ]
        self.assertFalse(is_schema_valid(candidate, self.input_schema))

    def test_repository_neutral_references_reject_absolute_and_uri_forms(self):
        forbidden_references = (
            r"C:\private\approval",
            "/tmp/private-approval",
            r"\\server\share\approval",
            r"\rooted\approval",
            "file:///C:/private/approval",
            "HTTPS://example.test/private-approval",
            "evidence/line\nbreak",
        )
        for reference in forbidden_references:
            candidate = valid_input()
            candidate["node_states"][0]["evidence_refs"] = [reference]
            self.assertFalse(is_schema_valid(candidate, self.input_schema), reference)
            candidate = valid_input()
            candidate["resource_availability"][0]["evidence_refs"] = [reference]
            self.assertFalse(is_schema_valid(candidate, self.input_schema), reference)
            candidate = valid_input()
            candidate["external_join_decisions"][0]["authority_ref"] = reference
            self.assertFalse(is_schema_valid(candidate, self.input_schema), reference)
            candidate = valid_input()
            candidate["external_join_decisions"][0]["evidence_refs"] = [reference]
            self.assertFalse(is_schema_valid(candidate, self.input_schema), reference)
            result = valid_result()
            result["node_decisions"][0]["blocking_refs"] = [reference]
            self.assertFalse(is_schema_valid(result, self.result_schema), reference)

    def test_duplicate_or_conflicting_identity_records_fail_closed(self):
        text = json.dumps(
            {
                "manifest": self.manifest,
                "input": self.input_schema,
            },
            sort_keys=True,
        ).lower()
        for identity in ("node_id", "resource_id", "join_id"):
            self.assertIn(f"each {identity}", text)
        for phrase in (
            "duplicate or conflicting records",
            "invalid required input",
            "required_input_invalid",
            "must not select",
            "majority",
            "default",
        ):
            self.assertIn(phrase, text)

    def test_semantic_boundaries_preserve_graph_and_terminal_meaning(self):
        text = json.dumps(
            {
                "manifest": self.manifest,
                "input": self.input_schema,
                "result": self.result_schema,
            },
            sort_keys=True,
        ).lower()
        for phrase in (
            "depends_on references nodes only",
            "join is an aggregation and decision boundary",
            "not a hidden scheduler edge",
            "must not invent a graph edge",
            "optional classification does not override explicit depends_on",
            "done_with_concerns does not satisfy required success",
            "handoff is a nonterminal workflow outcome",
            "succeeded is not project manager acceptance",
            "no_action_required remains evidence-bound",
            "blocked cannot be bypassed by majority or optional policy",
            "decision output, not runtime mutation",
            "host decides whether",
        ):
            self.assertIn(phrase, text)

    def test_contract_presence_is_inert_and_light_runtime_optionality_is_preserved(self):
        text = json.dumps(self.manifest, sort_keys=True).lower()
        for phrase in (
            "contract presence does not execute any node",
            "does not grant authority",
            "does not open or satisfy a human gate",
            "does not create a scheduler",
            "does not create runtime state",
            "host retains execution ownership",
            "light remains graph-artifact optional",
            "runtime remains optional",
        ):
            self.assertIn(phrase, text)

    def test_schemas_exclude_private_runtime_and_execution_payloads(self):
        schemas = (self.input_schema, self.result_schema, self.error_schema)
        names = property_names(schemas)
        self.assertTrue(FORBIDDEN_PROPERTIES.isdisjoint(names), FORBIDDEN_PROPERTIES & names)
        serialized = json.dumps(schemas, sort_keys=True)
        self.assertNotRegex(serialized, re.compile(r"(?:^|[\\s\"'])[A-Za-z]:[\\\\/]|(?:^|[\\s\"'])/(?:Users|home|tmp)/"))
        for schema, instance in (
            (self.input_schema, valid_input()),
            (self.result_schema, valid_result()),
            (self.error_schema, valid_error()),
        ):
            for forbidden in FORBIDDEN_PROPERTIES:
                candidate = dict(instance)
                candidate[forbidden] = "forbidden"
                self.assertFalse(is_schema_valid(candidate, schema), forbidden)

    def test_only_frozen_stage4a_manifest_changed(self):
        self.assertEqual(EXPECTED_STAGE4A_PATHS, changed_paths_since_baseline())
        manifests = {
            str(path.relative_to(REPOSITORY)).replace("\\", "/")
            for path in REPOSITORY.rglob("ready-resolution/v1/contract.json")
        }
        self.assertEqual(
            {
                "docs/contracts/ready-resolution/v1/contract.json",
                "sagekit/resources/contracts/ready-resolution/v1/contract.json",
            },
            manifests,
        )


if __name__ == "__main__":
    unittest.main()
