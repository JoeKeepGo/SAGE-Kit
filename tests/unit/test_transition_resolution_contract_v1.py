import copy
import hashlib
import json
import math
import re
import subprocess
import unittest
from pathlib import Path

from sagekit.graph_contract import NODE_STATUSES, validate_node_transition


REPOSITORY = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "20f209b137b294124b4492f960670716759be2fe"
CANONICAL = REPOSITORY / "docs/contracts/transition-resolution/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/transition-resolution/v1"
NODE_RESULT_SCHEMA = REPOSITORY / "docs/contracts/graph/v1/node-result.schema.json"
RESOURCE_NAMES = (
    "contract.json",
    "error.schema.json",
    "input.schema.json",
    "result.schema.json",
)
EXPECTED_STAGE4C1_PATHS = {
    "docs/contracts/transition-resolution/v1/contract.json",
    "docs/contracts/transition-resolution/v1/error.schema.json",
    "docs/contracts/transition-resolution/v1/input.schema.json",
    "docs/contracts/transition-resolution/v1/result.schema.json",
    "sagekit/resources/contracts/transition-resolution/v1/contract.json",
    "sagekit/resources/contracts/transition-resolution/v1/error.schema.json",
    "sagekit/resources/contracts/transition-resolution/v1/input.schema.json",
    "sagekit/resources/contracts/transition-resolution/v1/result.schema.json",
    "tests/unit/test_transition_resolution_contract_v1.py",
}
DEPENDENCY_DIGESTS = {
    "docs/contracts/graph/v1/contract.json": "fee6c97a067752e75755cf166cd94322cbe3775c298e474781f8814564356c76",
    "docs/contracts/graph/v1/node-result.schema.json": "a207e510f0b1749ea780494f53d64eca7d7a203c71a6e81db7b12243b5ea6379",
    "docs/contracts/runtime-state/v1/contract.json": "a27806a732dbf60b9c38b7f410e62ce6d93a38c9a99d222c27241ac57c6ed976",
    "docs/contracts/runtime-state/v1/state.schema.json": "0bc618412e1e2a8fbdb4691840477460294f38bf76b46dccef250979af29ce2e",
    "docs/contracts/runtime-state/v1/event.schema.json": "d7419489668ac25172e311d6ef53232746e7c778cd6af3ff2391765d13f6f4a9",
}
PROTECTED_PATHS = (
    "docs/contracts/graph/v1/contract.json",
    "docs/contracts/graph/v1/graph.schema.json",
    "docs/contracts/graph/v1/node-result.schema.json",
    "docs/contracts/runtime-state/v1/contract.json",
    "docs/contracts/runtime-state/v1/state.schema.json",
    "docs/contracts/runtime-state/v1/event.schema.json",
    "docs/contracts/ready-resolution/v1/contract.json",
    "docs/contracts/ready-resolution/v1/input.schema.json",
    "docs/contracts/ready-resolution/v1/result.schema.json",
    "docs/contracts/ready-resolution/v1/error.schema.json",
    "sagekit/resources/contracts/graph/v1/contract.json",
    "sagekit/resources/contracts/graph/v1/graph.schema.json",
    "sagekit/resources/contracts/graph/v1/node-result.schema.json",
    "sagekit/resources/contracts/runtime-state/v1/contract.json",
    "sagekit/resources/contracts/runtime-state/v1/state.schema.json",
    "sagekit/resources/contracts/runtime-state/v1/event.schema.json",
    "sagekit/resources/contracts/ready-resolution/v1/contract.json",
    "sagekit/resources/contracts/ready-resolution/v1/input.schema.json",
    "sagekit/resources/contracts/ready-resolution/v1/result.schema.json",
    "sagekit/resources/contracts/ready-resolution/v1/error.schema.json",
)
INPUT_REQUIRED = {
    "schema_id",
    "schema_version",
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
    "node_result",
}
RESULT_REQUIRED = {
    "schema_id",
    "schema_version",
    "disposition",
    "input_digest",
    "node_result_digest",
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
    "next_status",
    "reason_code",
    "transition_allowed",
    "authority_decision_required",
    "grants_execution_authority",
    "grants_graph_mutation_authority",
    "grants_gate_authority",
    "grants_write_authority",
}
ERROR_CODES = {
    "REQUIRED_INPUT_INVALID",
    "INPUT_TOO_LARGE",
    "GRAPH_BINDING_MISMATCH",
    "NODE_BINDING_MISMATCH",
    "NODE_RESULT_INVALID",
    "TRANSITION_NOT_ALLOWED",
    "AUTHORITY_CHANGE_STATUS_INVALID",
    "RESULT_TOO_LARGE",
}
TERMINAL_STATUSES = {
    "SUCCEEDED",
    "NO_ACTION_REQUIRED",
    "FAILED",
    "HANDOFF",
    "BLOCKED",
    "CANCELLED",
    "DONE_WITH_CONCERNS",
}
NODE_RESULT_DOMAIN = b"sagekit-node-result-v1\0"
TRANSITION_INPUT_DOMAIN = b"sagekit-transition-resolution-input-v1\0"
NODE_RESULT_VECTOR_SHA256 = "bec9a2c92f462c99ee6a5389edf8a06cb2479433e89fd7286d8ea0702a90efb6"
TRANSITION_INPUT_VECTOR_SHA256 = "e6ec15448d9c77ec74a77b430d9c7bfa2fd2b750c523f44fcfa1eafb3da1cd69"
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
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def normalize_json_integers(value):
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("NaN and Infinity are not JSON numbers")
        if not value.is_integer():
            raise ValueError("only mathematical JSON integers are admitted")
        return int(value)
    if isinstance(value, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("surrogate code points are not Unicode scalar values")
    if isinstance(value, dict):
        return {
            normalize_json_integers(key): normalize_json_integers(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [normalize_json_integers(child) for child in value]
    return value


def canonical_json_bytes(value):
    normalized = normalize_json_integers(value)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_digest(domain, value):
    return hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def resolve_local_ref(root, reference):
    value = root
    for component in reference[2:].split("/"):
        value = value[component.replace("~1", "/").replace("~0", "~")]
    return value


def json_equal(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def is_schema_valid(instance, schema, root=None, registry=None):
    """Dependency-free evaluator for the JSON Schema keywords used by this contract."""
    root = schema if root is None else root
    registry = {} if registry is None else registry
    if isinstance(schema, bool):
        return schema
    if "$ref" in schema:
        reference = schema["$ref"]
        if reference.startswith("#/"):
            target = resolve_local_ref(root, reference)
            if not is_schema_valid(instance, target, root, registry):
                return False
        else:
            if reference not in registry:
                raise AssertionError(f"unregistered schema reference: {reference}")
            target = registry[reference]
            if not is_schema_valid(instance, target, target, registry):
                return False
    if "allOf" in schema and not all(
        is_schema_valid(instance, child, root, registry) for child in schema["allOf"]
    ):
        return False
    if "anyOf" in schema and not any(
        is_schema_valid(instance, child, root, registry) for child in schema["anyOf"]
    ):
        return False
    if "oneOf" in schema and sum(
        is_schema_valid(instance, child, root, registry) for child in schema["oneOf"]
    ) != 1:
        return False
    if "not" in schema and is_schema_valid(instance, schema["not"], root, registry):
        return False
    if "if" in schema:
        branch = (
            "then"
            if is_schema_valid(instance, schema["if"], root, registry)
            else "else"
        )
        if branch in schema and not is_schema_valid(
            instance, schema[branch], root, registry
        ):
            return False
    if "const" in schema and not json_equal(instance, schema["const"]):
        return False
    if "enum" in schema and not any(
        json_equal(instance, item) for item in schema["enum"]
    ):
        return False

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        type_matches = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "integer": lambda value: (
                type(value) is int
                or (
                    type(value) is float
                    and math.isfinite(value)
                    and value.is_integer()
                )
            ),
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
            encoded = [
                json.dumps(item, sort_keys=True, ensure_ascii=False)
                for item in instance
            ]
            if len(encoded) != len(set(encoded)):
                return False
        if "items" in schema and not all(
            is_schema_valid(item, schema["items"], root, registry)
            for item in instance
        ):
            return False

    if isinstance(instance, dict):
        if any(name not in instance for name in schema.get("required", [])):
            return False
        properties = schema.get("properties", {})
        for name, value in instance.items():
            if name in properties and not is_schema_valid(
                value, properties[name], root, registry
            ):
                return False
            if name not in properties and schema.get("additionalProperties") is False:
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


def object_property_names(schema):
    names = set()
    for value in walk(schema):
        if isinstance(value, dict) and isinstance(value.get("properties"), dict):
            names.update(value["properties"])
    return names


def node_result_vector():
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


def transition_input_vector():
    result = {
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
    }
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
        "node_result": result,
    }


def valid_input(status="SUCCEEDED", *, authority_change=False):
    payload = transition_input_vector()
    payload.update(
        graph_id="graph/α",
        graph_generation=1,
        graph_digest="a" * 64,
        run_id="run/α",
        authority_id="authority/α",
        controller_id="controller/α",
        node_id="node/α",
        attempt_id="attempt/α",
        state_revision=3,
        last_event_sequence=8,
        previous_status="RUNNING",
    )
    payload["node_result"] = {
        "schema_id": "urn:sagekit:graph-contract:v1:node-result",
        "schema_version": 1,
        "node_id": payload["node_id"],
        "status": status,
        "changed_paths": [],
        "evidence_refs": [],
        "findings": [],
        "authority_change": authority_change,
        "proposed_next_nodes": [],
    }
    if status == "NO_ACTION_REQUIRED":
        payload["node_result"].update(
            inspected_scope=["scope/α"],
            decision="No action was required.",
            evidence_refs=["evidence/α"],
        )
    if authority_change:
        payload["node_result"]["decision"] = "Request a bounded authority decision."
    return payload


def valid_result(status="SUCCEEDED", *, authority_change=False):
    source = valid_input(
        "HANDOFF" if authority_change else status,
        authority_change=authority_change,
    )
    return {
        "schema_id": "urn:sagekit:transition-resolution:v1:result",
        "schema_version": 1,
        "disposition": (
            "APPLY_HANDOFF_AND_REQUEST_AUTHORITY"
            if authority_change
            else "APPLY_TRANSITION"
        ),
        "input_digest": content_digest(TRANSITION_INPUT_DOMAIN, source),
        "node_result_digest": content_digest(
            NODE_RESULT_DOMAIN, source["node_result"]
        ),
        "graph_id": source["graph_id"],
        "graph_generation": source["graph_generation"],
        "graph_digest": source["graph_digest"],
        "run_id": source["run_id"],
        "authority_id": source["authority_id"],
        "controller_id": source["controller_id"],
        "node_id": source["node_id"],
        "attempt_id": source["attempt_id"],
        "state_revision": source["state_revision"],
        "last_event_sequence": source["last_event_sequence"],
        "previous_status": source["previous_status"],
        "next_status": source["node_result"]["status"],
        "reason_code": (
            "AUTHORITY_CHANGE_HANDOFF_REQUIRED"
            if authority_change
            else "NODE_RESULT_STATUS_APPLIED"
        ),
        "transition_allowed": True,
        "authority_decision_required": authority_change,
        "grants_execution_authority": False,
        "grants_graph_mutation_authority": False,
        "grants_gate_authority": False,
        "grants_write_authority": False,
    }


def valid_error():
    return {
        "schema_id": "urn:sagekit:transition-resolution:v1:error",
        "schema_version": 1,
        "error_code": "TRANSITION_NOT_ALLOWED",
        "issues": [
            {
                "path": "$.previous_status",
                "code": "TRANSITION_NOT_ALLOWED",
                "message": "The proposed transition is not allowed.",
            }
        ],
    }


class TransitionResolutionContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = {name: CANONICAL / name for name in RESOURCE_NAMES}
        cls.packaged = {name: PACKAGED / name for name in RESOURCE_NAMES}
        missing = [
            str(path.relative_to(REPOSITORY)).replace("\\", "/")
            for _, path in (*cls.canonical.items(), *cls.packaged.items())
            if not path.is_file()
        ]
        if missing:
            raise AssertionError(
                "Stage 4C1 contract TDD RED: transition resources are missing: "
                + ", ".join(missing)
            )
        cls.contract = load_json(cls.canonical["contract.json"])
        cls.input_schema = load_json(cls.canonical["input.schema.json"])
        cls.result_schema = load_json(cls.canonical["result.schema.json"])
        cls.error_schema = load_json(cls.canonical["error.schema.json"])
        cls.node_result_schema = load_json(NODE_RESULT_SCHEMA)
        cls.registry = {
            cls.node_result_schema["$id"]: cls.node_result_schema,
        }

    def input_valid(self, value):
        return is_schema_valid(
            value, self.input_schema, registry=self.registry
        )

    def test_resources_exist_parse_and_packaged_mirrors_have_exact_byte_parity(self):
        self.assertEqual(
            RESOURCE_NAMES, tuple(sorted(path.name for path in CANONICAL.iterdir()))
        )
        self.assertEqual(
            RESOURCE_NAMES, tuple(sorted(path.name for path in PACKAGED.iterdir()))
        )
        for name in RESOURCE_NAMES:
            load_json(self.canonical[name])
            load_json(self.packaged[name])
            self.assertEqual(
                self.canonical[name].read_bytes(), self.packaged[name].read_bytes()
            )

    def test_stable_contract_and_schema_urns(self):
        self.assertEqual(
            "urn:sagekit:transition-resolution:v1",
            self.contract["contract_id"],
        )
        self.assertEqual(
            "urn:sagekit:transition-resolution:v1:input",
            self.input_schema["$id"],
        )
        self.assertEqual(
            "urn:sagekit:transition-resolution:v1:result",
            self.result_schema["$id"],
        )
        self.assertEqual(
            "urn:sagekit:transition-resolution:v1:error",
            self.error_schema["$id"],
        )

    def test_manifest_binds_resource_and_dependency_canonical_digests(self):
        for key, name in (
            ("input_schema", "input.schema.json"),
            ("result_schema", "result.schema.json"),
            ("error_schema", "error.schema.json"),
        ):
            self.assertEqual(
                canonical_sha256(self.canonical[name]),
                self.contract["resources"][key]["canonical_sha256"],
            )
        dependency_records = self.contract["dependencies"]
        expected = {
            "graph_contract_v1": DEPENDENCY_DIGESTS[
                "docs/contracts/graph/v1/contract.json"
            ],
            "node_result_v1": DEPENDENCY_DIGESTS[
                "docs/contracts/graph/v1/node-result.schema.json"
            ],
            "runtime_state_contract_v1": DEPENDENCY_DIGESTS[
                "docs/contracts/runtime-state/v1/contract.json"
            ],
            "runtime_state_v1": DEPENDENCY_DIGESTS[
                "docs/contracts/runtime-state/v1/state.schema.json"
            ],
            "runtime_event_v1": DEPENDENCY_DIGESTS[
                "docs/contracts/runtime-state/v1/event.schema.json"
            ],
        }
        for key, digest in expected.items():
            self.assertEqual(digest, dependency_records[key]["canonical_sha256"])
        for path, digest in DEPENDENCY_DIGESTS.items():
            self.assertEqual(digest, canonical_sha256(REPOSITORY / path))

    def test_input_exact_fields_closed_shape_and_existing_node_result_reference(self):
        self.assertEqual(INPUT_REQUIRED, set(self.input_schema["required"]))
        self.assertEqual(INPUT_REQUIRED, set(self.input_schema["properties"]))
        self.assertFalse(self.input_schema["additionalProperties"])
        self.assertEqual(
            "urn:sagekit:graph-contract:v1:node-result",
            self.input_schema["properties"]["node_result"]["$ref"],
        )
        payload = valid_input()
        self.assertTrue(self.input_valid(payload))
        payload["unknown"] = True
        self.assertFalse(self.input_valid(payload))

    def test_snapshot_identity_and_stale_apply_bindings_are_required(self):
        binding = set(self.contract["snapshot_binding"]["result_revalidation_fields"])
        self.assertEqual(
            {
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
            },
            binding,
        )
        self.assertTrue(binding.issubset(self.input_schema["required"]))
        self.assertTrue(binding.issubset(self.result_schema["required"]))
        self.assertEqual(
            "host_runtime_writer",
            self.contract["race_and_apply_boundary"]["revalidation_owner"],
        )
        self.assertEqual(
            "reject_stale_result",
            self.contract["race_and_apply_boundary"]["snapshot_changed_action"],
        )

    def test_node_binding_mismatch_is_fail_closed(self):
        payload = valid_input()
        payload["node_result"]["node_id"] = "other/node"
        rule = self.contract["semantic_validation"]["node_binding"]
        self.assertEqual("$.node_id", rule["left"])
        self.assertEqual("$.node_result.node_id", rule["right"])
        self.assertEqual("NODE_BINDING_MISMATCH", rule["error_code"])
        self.assertNotEqual(payload["node_id"], payload["node_result"]["node_id"])

    def test_nonempty_attempt_and_bool_as_int_rejection(self):
        payload = valid_input()
        payload["attempt_id"] = ""
        self.assertFalse(self.input_valid(payload))
        for field in ("graph_generation", "state_revision", "last_event_sequence"):
            with self.subTest(field=field):
                payload = valid_input()
                payload[field] = True
                self.assertFalse(self.input_valid(payload))
        for field in ("state_revision", "last_event_sequence"):
            with self.subTest(field=field):
                payload = valid_input()
                payload[field] = -1
                self.assertFalse(self.input_valid(payload))

    def test_all_twelve_existing_node_statuses_are_reused(self):
        self.assertEqual(
            set(NODE_STATUSES),
            set(self.input_schema["$defs"]["node_status"]["enum"]),
        )
        self.assertEqual(
            set(NODE_STATUSES),
            set(self.result_schema["$defs"]["node_status"]["enum"]),
        )
        self.assertEqual(
            set(NODE_STATUSES),
            set(self.result_schema["$defs"]["node_status"]["enum"]),
        )

    def test_ordinary_apply_transition_conditional(self):
        result = valid_result()
        self.assertTrue(is_schema_valid(result, self.result_schema))
        self.assertEqual("APPLY_TRANSITION", result["disposition"])
        self.assertEqual("SUCCEEDED", result["next_status"])
        self.assertFalse(result["authority_decision_required"])
        result["authority_decision_required"] = True
        self.assertFalse(is_schema_valid(result, self.result_schema))

    def test_authority_change_handoff_conditional(self):
        payload = valid_input("HANDOFF", authority_change=True)
        self.assertTrue(self.input_valid(payload))
        result = valid_result(authority_change=True)
        self.assertTrue(is_schema_valid(result, self.result_schema))
        self.assertEqual(
            "APPLY_HANDOFF_AND_REQUEST_AUTHORITY", result["disposition"]
        )
        self.assertEqual("HANDOFF", result["next_status"])
        self.assertTrue(result["authority_decision_required"])

    def test_authority_change_success_false_green_is_rejected(self):
        for status in (
            "SUCCEEDED",
            "NO_ACTION_REQUIRED",
            "DONE_WITH_CONCERNS",
        ):
            with self.subTest(status=status):
                payload = valid_input(status, authority_change=True)
                self.assertFalse(self.input_valid(payload))
        rule = self.contract["semantic_validation"]["authority_change_status"]
        self.assertEqual("HANDOFF", rule["required_status"])
        self.assertEqual("AUTHORITY_CHANGE_STATUS_INVALID", rule["error_code"])

    def test_result_required_fields_dispositions_and_authority_constants(self):
        self.assertEqual(RESULT_REQUIRED, set(self.result_schema["required"]))
        self.assertEqual(RESULT_REQUIRED, set(self.result_schema["properties"]))
        self.assertFalse(self.result_schema["additionalProperties"])
        self.assertEqual(
            {
                "APPLY_TRANSITION",
                "APPLY_HANDOFF_AND_REQUEST_AUTHORITY",
            },
            set(self.result_schema["properties"]["disposition"]["enum"]),
        )
        self.assertIs(
            True, self.result_schema["properties"]["transition_allowed"]["const"]
        )
        for field in (
            "grants_execution_authority",
            "grants_graph_mutation_authority",
            "grants_gate_authority",
            "grants_write_authority",
        ):
            self.assertIs(False, self.result_schema["properties"][field]["const"])

    def test_result_expresses_only_validate_node_transition_allowed_pairs(self):
        for previous in NODE_STATUSES:
            for proposed in NODE_STATUSES:
                with self.subTest(previous=previous, proposed=proposed):
                    result = valid_result(proposed)
                    result["previous_status"] = previous
                    expected = validate_node_transition(previous, proposed).allowed
                    self.assertEqual(
                        expected, is_schema_valid(result, self.result_schema)
                    )
        self.assertEqual(
            "validate_node_transition",
            self.contract["transition_legality"]["owner"],
        )

    def test_terminal_previous_status_cannot_produce_result(self):
        for previous in TERMINAL_STATUSES:
            with self.subTest(previous=previous):
                result = valid_result()
                result["previous_status"] = previous
                self.assertFalse(is_schema_valid(result, self.result_schema))

    def test_no_action_and_done_with_concerns_remain_independent(self):
        for status in ("NO_ACTION_REQUIRED", "DONE_WITH_CONCERNS"):
            with self.subTest(status=status):
                result = valid_result(status)
                self.assertTrue(is_schema_valid(result, self.result_schema))
                self.assertEqual(status, result["next_status"])
                self.assertNotEqual("SUCCEEDED", result["next_status"])

    def test_proposed_next_nodes_are_digest_bound_proposals_without_graph_authority(self):
        payload = valid_input()
        payload["node_result"]["proposed_next_nodes"] = ["next/β", "next/α"]
        digest = content_digest(TRANSITION_INPUT_DOMAIN, payload)
        changed = copy.deepcopy(payload)
        changed["node_result"]["proposed_next_nodes"].reverse()
        self.assertNotEqual(digest, content_digest(TRANSITION_INPUT_DOMAIN, changed))
        result = valid_result()
        self.assertFalse(result["grants_graph_mutation_authority"])
        boundary = self.contract["semantic_boundaries"]["graph_mutation"]
        for word in ("activate", "create", "execute", "schedule"):
            self.assertIn(word, boundary)

    def test_fixed_independent_digest_vectors(self):
        self.assertEqual(
            NODE_RESULT_VECTOR_SHA256,
            content_digest(NODE_RESULT_DOMAIN, node_result_vector()),
        )
        self.assertEqual(
            TRANSITION_INPUT_VECTOR_SHA256,
            content_digest(TRANSITION_INPUT_DOMAIN, transition_input_vector()),
        )
        vectors = self.contract["canonical_digests"]["test_vectors"]
        self.assertEqual(node_result_vector(), vectors["node_result"]["value"])
        self.assertEqual(
            NODE_RESULT_VECTOR_SHA256,
            vectors["node_result"]["expected_sha256"],
        )
        self.assertEqual(
            transition_input_vector(), vectors["transition_input"]["value"]
        )
        self.assertEqual(
            TRANSITION_INPUT_VECTOR_SHA256,
            vectors["transition_input"]["expected_sha256"],
        )

    def test_canonical_object_keys_are_deterministic_and_array_order_is_preserved(self):
        original = transition_input_vector()
        reversed_keys = dict(reversed(list(original.items())))
        self.assertEqual(
            content_digest(TRANSITION_INPUT_DOMAIN, original),
            content_digest(TRANSITION_INPUT_DOMAIN, reversed_keys),
        )
        reordered_array = copy.deepcopy(original)
        reordered_array["node_result"]["proposed_next_nodes"].reverse()
        self.assertNotEqual(
            content_digest(TRANSITION_INPUT_DOMAIN, original),
            content_digest(TRANSITION_INPUT_DOMAIN, reordered_array),
        )

    def test_json_integer_semantics_normalize_equivalent_lexemes_and_reject_non_json_numbers(self):
        expected = b'{"value":1}'
        self.assertEqual(expected, canonical_json_bytes({"value": 1}))
        self.assertEqual(expected, canonical_json_bytes({"value": 1.0}))
        self.assertEqual(
            expected,
            canonical_json_bytes(json.loads('{"value":1e0}')),
        )
        self.assertEqual(
            b'{"value":0}',
            canonical_json_bytes(json.loads('{"value":-0.0}')),
        )
        payload = valid_input()
        for field in ("graph_generation", "state_revision", "last_event_sequence"):
            with self.subTest(field=field):
                equivalent = copy.deepcopy(payload)
                equivalent[field] = 1.0
                self.assertTrue(self.input_valid(equivalent))
        for value in (True, False, math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                invalid = valid_input()
                invalid["state_revision"] = value
                self.assertFalse(self.input_valid(invalid))
                if type(value) is float:
                    with self.assertRaises(ValueError):
                        canonical_json_bytes({"value": value})
        with self.assertRaises(ValueError):
            canonical_json_bytes({"value": 1.5})

    def test_unicode_non_bmp_surrogates_and_opaque_identity_preservation(self):
        vector = transition_input_vector()
        encoded = canonical_json_bytes(vector)
        self.assertIn("𐀀".encode("utf-8"), encoded)
        self.assertNotIn(b"\\ud800\\udc00", encoded.lower())
        with self.assertRaises(ValueError):
            canonical_json_bytes({"node_id": "\ud800"})
        long_identity = "!/" + ("节点/😀/" * 400)
        payload = valid_input()
        for field in (
            "graph_id",
            "run_id",
            "authority_id",
            "controller_id",
            "node_id",
            "attempt_id",
        ):
            payload[field] = long_identity
        payload["node_result"]["node_id"] = long_identity
        self.assertTrue(self.input_valid(payload))
        self.assertIn(
            "no trim, case-fold, path normalization, or Unicode normalization",
            self.contract["canonical_digests"]["opaque_string_rule"],
        )

    def test_input_result_and_error_canonical_byte_bounds(self):
        self.assertEqual(
            {
                "input_max_canonical_bytes": 16777216,
                "result_max_canonical_bytes": 16777216,
                "error_max_canonical_bytes": 1048576,
            },
            self.contract["canonical_byte_budgets"],
        )
        self.assertIn("16777216", self.input_schema["description"])
        self.assertIn("16777216", self.result_schema["description"])
        self.assertIn("1048576", self.error_schema["description"])

    def test_error_contract_is_closed_bounded_and_has_stable_codes(self):
        self.assertFalse(self.error_schema["additionalProperties"])
        self.assertEqual(ERROR_CODES, set(self.error_schema["properties"]["error_code"]["enum"]))
        issues = self.error_schema["properties"]["issues"]
        self.assertEqual(1, issues["minItems"])
        self.assertEqual(100, issues["maxItems"])
        issue = self.error_schema["$defs"]["issue"]
        self.assertEqual(
            {"path", "code", "message"}, set(issue["required"])
        )
        self.assertFalse(issue["additionalProperties"])
        for field in ("path", "code", "message"):
            self.assertGreater(issue["properties"][field]["maxLength"], 0)
        self.assertTrue(is_schema_valid(valid_error(), self.error_schema))

    def test_result_and_error_are_strictly_mutually_exclusive_without_partial_result(self):
        result = valid_result()
        error = valid_error()
        self.assertTrue(is_schema_valid(result, self.result_schema))
        self.assertFalse(is_schema_valid(result, self.error_schema))
        self.assertTrue(is_schema_valid(error, self.error_schema))
        self.assertFalse(is_schema_valid(error, self.result_schema))
        partial = copy.deepcopy(error)
        partial["next_status"] = "HANDOFF"
        self.assertFalse(is_schema_valid(partial, self.error_schema))
        self.assertEqual(
            "one_of_result_or_error",
            self.contract["output_contract"]["exclusivity"],
        )

    def test_privacy_and_restricted_fields_are_rejected(self):
        for schema in (self.input_schema, self.result_schema, self.error_schema):
            self.assertTrue(
                FORBIDDEN_PROPERTIES.isdisjoint(object_property_names(schema))
            )
        for forbidden in FORBIDDEN_PROPERTIES:
            with self.subTest(forbidden=forbidden):
                error = valid_error()
                error[forbidden] = "not allowed"
                self.assertFalse(is_schema_valid(error, self.error_schema))
        privacy = self.contract["semantic_boundaries"]["privacy"]
        for phrase in (
            "private reasoning",
            "transcript",
            "stdout",
            "stderr",
            "secret",
            "credential",
            "environment dump",
        ):
            self.assertIn(phrase, privacy)

    def test_schema_presence_creates_no_runtime_or_graph_behavior(self):
        inert = self.contract["semantic_boundaries"]
        for key in (
            "runtime_mutation",
            "graph_mutation",
            "authority",
            "ready_resolver",
        ):
            self.assertIn(key, inert)
        self.assertIn("does not call", inert["ready_resolver"])
        self.assertIn("does not create", inert["runtime_mutation"])
        self.assertIn("pure decision", inert["authority"])
        self.assertNotIn("resolver.py", " ".join(EXPECTED_STAGE4C1_PATHS))

    def test_exact_nine_file_manifest_and_protected_dependency_blobs(self):
        committed = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                f"{BASELINE_COMMIT}..HEAD",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        working = [line[3:].replace("\\", "/") for line in status]
        self.assertEqual(EXPECTED_STAGE4C1_PATHS, set(committed) | set(working))
        self.assertEqual(9, len(EXPECTED_STAGE4C1_PATHS))
        for path in PROTECTED_PATHS:
            with self.subTest(path=path):
                baseline_blob = subprocess.run(
                    ["git", "rev-parse", f"{BASELINE_COMMIT}:{path}"],
                    cwd=REPOSITORY,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                current_blob = subprocess.run(
                    ["git", "hash-object", "--", path],
                    cwd=REPOSITORY,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                self.assertEqual(baseline_blob, current_blob)


if __name__ == "__main__":
    unittest.main()
