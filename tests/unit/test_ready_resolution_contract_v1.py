import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "9b4ce24422bb1f0b630dde5f21d6d1a798f80854"
CANONICAL = REPOSITORY / "docs/contracts/ready-resolution/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/ready-resolution/v1"
RESOURCE_NAMES = (
    "contract.json",
    "input.schema.json",
    "result.schema.json",
)
EXPECTED_STAGE4A_PATHS = {
    "docs/contracts/ready-resolution/v1/contract.json",
    "docs/contracts/ready-resolution/v1/input.schema.json",
    "docs/contracts/ready-resolution/v1/result.schema.json",
    "sagekit/resources/contracts/ready-resolution/v1/contract.json",
    "sagekit/resources/contracts/ready-resolution/v1/input.schema.json",
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
    "REQUIRED_INPUT_INVALID",
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
        "graph_disposition": "READY",
        "node_decisions": [
            {
                "node_id": "阶段/节点 α",
                "disposition": "READY",
                "reason_codes": ["DEPENDENCIES_SATISFIED"],
                "blocking_refs": [],
            }
        ],
        "join_decisions": [],
        "summary": summary,
    }


class ReadyResolutionContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = {name: CANONICAL / name for name in RESOURCE_NAMES}
        cls.packaged = {name: PACKAGED / name for name in RESOURCE_NAMES}
        missing = [
            str(path.relative_to(REPOSITORY)).replace("\\", "/")
            for path in (*cls.canonical.values(), *cls.packaged.values())
            if not path.is_file()
        ]
        if missing:
            raise AssertionError(
                "Stage 4A native TDD RED: the six contract resources do not exist: "
                + ", ".join(missing)
            )
        cls.manifest = load_json(cls.canonical["contract.json"])
        cls.input_schema = load_json(cls.canonical["input.schema.json"])
        cls.result_schema = load_json(cls.canonical["result.schema.json"])

    def test_six_resources_parse_and_use_stable_identities(self):
        for path in (*self.canonical.values(), *self.packaged.values()):
            load_json(path)
        self.assertEqual("urn:sagekit:ready-resolution:v1", self.manifest["contract_id"])
        self.assertEqual("urn:sagekit:ready-resolution:v1:input", self.input_schema["$id"])
        self.assertEqual("urn:sagekit:ready-resolution:v1:result", self.result_schema["$id"])
        self.assertEqual(1, self.input_schema["properties"]["schema_version"]["const"])
        self.assertEqual(1, self.result_schema["properties"]["schema_version"]["const"])

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
        self.assertEqual({"input_schema", "result_schema"}, set(resources))
        for key, name in (("input_schema", "input.schema.json"), ("result_schema", "result.schema.json")):
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
                "graph_disposition",
                "node_decisions",
                "join_decisions",
                "summary",
            },
            set(self.result_schema["required"]),
        )
        self.assertEqual(
            {"node_id", "disposition", "reason_codes", "blocking_refs"},
            set(self.result_schema["$defs"]["node_decision"]["required"]),
        )
        self.assertEqual(
            {"join_id", "disposition", "reason_codes", "blocking_refs"},
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
        reason_codes = set(self.result_schema["$defs"]["reason_code"]["enum"])
        self.assertTrue(REQUIRED_REASON_CODES.issubset(reason_codes))

    def test_every_object_is_closed_and_every_array_is_bounded(self):
        for name, schema in (("input", self.input_schema), ("result", self.result_schema)):
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
        self.assertEqual({"type": "string", "minLength": 1}, node_id)
        self.assertEqual({"type": "string", "minLength": 1}, self.input_schema["$defs"]["graph_id"])
        self.assertEqual({"type": "string", "minLength": 1}, self.result_schema["$defs"]["graph_id"])
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
                "blocking_refs": ["join/manual-review"],
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
        schemas = (self.input_schema, self.result_schema)
        names = property_names(schemas)
        self.assertTrue(FORBIDDEN_PROPERTIES.isdisjoint(names), FORBIDDEN_PROPERTIES & names)
        serialized = json.dumps(schemas, sort_keys=True)
        self.assertNotRegex(serialized, re.compile(r"(?:^|[\\s\"'])[A-Za-z]:[\\\\/]|(?:^|[\\s\"'])/(?:Users|home|tmp)/"))
        for schema, instance in (
            (self.input_schema, valid_input()),
            (self.result_schema, valid_result()),
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
