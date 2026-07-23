import hashlib
import json
import re
import subprocess
import unittest
from datetime import datetime
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "fee1246560bf358275c9f213f908b9045a4bf7e7"
CANONICAL = REPOSITORY / "docs/contracts/runtime-state/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/runtime-state/v1"
RESOURCE_NAMES = (
    "contract.json",
    "event.schema.json",
    "state.schema.json",
)
EXPECTED_STAGE3D_PATHS = {
    "docs/contracts/runtime-state/v1/contract.json",
    "docs/contracts/runtime-state/v1/event.schema.json",
    "docs/contracts/runtime-state/v1/state.schema.json",
    "sagekit/resources/contracts/runtime-state/v1/contract.json",
    "sagekit/resources/contracts/runtime-state/v1/event.schema.json",
    "sagekit/resources/contracts/runtime-state/v1/state.schema.json",
    "sagekit/runtime_store.py",
    "sagekit/runtime_recovery.py",
    "sagekit/runtime_views.py",
    "tests/unit/test_runtime_state_contract_v1.py",
    "tests/unit/test_runtime_store.py",
    "tests/unit/test_runtime_recovery.py",
    "tests/unit/test_runtime_views.py",
}
GRAPH_RESOURCE_DIGESTS = {
    "contract.json": "fee6c97a067752e75755cf166cd94322cbe3775c298e474781f8814564356c76",
    "graph.schema.json": "510f9d4a960aba78f80ac0ec35ac37504d992702528acad3c9f96279cab1824e",
    "node-result.schema.json": "a207e510f0b1749ea780494f53d64eca7d7a203c71a6e81db7b12243b5ea6379",
}
RUN_STATUSES = {
    "INITIALIZED",
    "RUNNING",
    "WAITING_RESOURCE",
    "NEEDS_CORRECTION",
    "HANDOFF",
    "BLOCKED",
    "COMPLETED",
    "CANCELLED",
    "RECOVERING",
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
EVENT_TYPES = {
    "RUN_INITIALIZED",
    "GRAPH_BOUND",
    "RUN_STARTED",
    "NODE_READY",
    "NODE_STARTED",
    "NODE_WAITING_RESOURCE",
    "NODE_RESULT_RECORDED",
    "NODE_TRANSITIONED",
    "RECOVERY_STARTED",
    "RECOVERY_COMPLETED",
    "RUN_HANDOFF",
    "RUN_BLOCKED",
    "RUN_COMPLETED",
    "RUN_CANCELLED",
}
STATE_REQUIRED = {
    "schema_id",
    "schema_version",
    "run_id",
    "graph_digest",
    "graph_generation",
    "revision",
    "last_event_sequence",
    "run_status",
    "authority_id",
    "controller_id",
    "node_states",
}
NODE_STATE_REQUIRED = {
    "node_id",
    "status",
    "attempt_id",
    "last_event_sequence",
    "evidence_refs",
}
EVENT_REQUIRED = {
    "schema_id",
    "schema_version",
    "event_id",
    "run_id",
    "sequence",
    "graph_digest",
    "event_type",
    "authority_id",
    "actor_id",
    "observed_at",
    "reason_code",
    "evidence_refs",
    "artifact_refs",
}
FORBIDDEN_PROPERTIES = {
    "chain_of_thought",
    "reasoning",
    "prompt",
    "chat_transcript",
    "tool_transcript",
    "stdout",
    "stderr",
    "command_output",
    "complete_command_output",
    "credentials",
    "secrets",
    "environment_dump",
    "payload",
    "active_context",
    "project_profile",
    "project_design",
    "closeout",
    "accepted_history",
    "milestone_document",
    "phase_document",
    "graph",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
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
    """Small dependency-free evaluator for the schema keywords used by this contract test."""
    root = schema if root is None else root
    if "$ref" in schema and not is_schema_valid(instance, resolve_local_ref(root, schema["$ref"]), root):
        return False
    if "allOf" in schema and not all(is_schema_valid(instance, child, root) for child in schema["allOf"]):
        return False
    if "anyOf" in schema and not any(is_schema_valid(instance, child, root) for child in schema["anyOf"]):
        return False
    if "oneOf" in schema and sum(is_schema_valid(instance, child, root) for child in schema["oneOf"]) != 1:
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
        if schema.get("format") == "date-time":
            if not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", instance):
                return False
            try:
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError:
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
            serialized = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in instance]
            if len(serialized) != len(set(serialized)):
                return False
        if "items" in schema and not all(is_schema_valid(item, schema["items"], root) for item in instance):
            return False

    if isinstance(instance, dict):
        if not set(schema.get("required", ())).issubset(instance):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and not set(instance).issubset(properties):
            return False
        for name, value in instance.items():
            if name in properties and not is_schema_valid(value, properties[name], root):
                return False
    return True


def valid_state():
    return {
        "schema_id": "urn:sagekit:runtime-state-contract:v1:state",
        "schema_version": 1,
        "run_id": "run:authority-graph",
        "graph_digest": "1" * 64,
        "graph_generation": 1,
        "revision": 0,
        "last_event_sequence": 0,
        "run_status": "INITIALIZED",
        "authority_id": "authority:stage3a",
        "controller_id": "controller:root",
        "node_states": [
            {
                "node_id": "node:contract",
                "status": "PENDING",
                "attempt_id": None,
                "last_event_sequence": 0,
                "evidence_refs": [],
            }
        ],
    }


def valid_event():
    return {
        "schema_id": "urn:sagekit:runtime-state-contract:v1:event",
        "schema_version": 1,
        "event_id": "event:run-authority-graph:1",
        "run_id": "run:authority-graph",
        "sequence": 1,
        "graph_digest": "1" * 64,
        "event_type": "RUN_INITIALIZED",
        "authority_id": "authority:stage3a",
        "actor_id": "actor:controller-root",
        "observed_at": "2026-07-23T12:00:00+12:00",
        "reason_code": "RUN_CREATED",
        "evidence_refs": [],
        "artifact_refs": [],
    }


class RuntimeStateContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [
            path
            for directory in (CANONICAL, PACKAGED)
            for name in RESOURCE_NAMES
            if not (path := directory / name).is_file()
        ]
        if missing:
            raise AssertionError(
                "Stage 3A resources are not implemented: "
                + ", ".join(path.relative_to(REPOSITORY).as_posix() for path in missing)
            )
        cls.canonical = {name: CANONICAL / name for name in RESOURCE_NAMES}
        cls.packaged = {name: PACKAGED / name for name in RESOURCE_NAMES}
        cls.manifest = load_json(cls.canonical["contract.json"])
        cls.state = load_json(cls.canonical["state.schema.json"])
        cls.event = load_json(cls.canonical["event.schema.json"])

    def test_canonical_and_packaged_resources_are_exact_byte_identical_families(self):
        self.assertEqual(RESOURCE_NAMES, tuple(sorted(path.name for path in CANONICAL.iterdir())))
        self.assertEqual(RESOURCE_NAMES, tuple(sorted(path.name for path in PACKAGED.iterdir())))
        for name in RESOURCE_NAMES:
            self.assertEqual(self.canonical[name].read_bytes(), self.packaged[name].read_bytes())

    def test_resources_parse_and_use_stable_urns(self):
        for path in (*self.canonical.values(), *self.packaged.values()):
            load_json(path)
        self.assertEqual("urn:sagekit:runtime-state-contract:v1", self.manifest["contract_id"])
        self.assertEqual("urn:sagekit:runtime-state-contract:v1:state", self.state["$id"])
        self.assertEqual("urn:sagekit:runtime-state-contract:v1:event", self.event["$id"])
        self.assertEqual(self.state["$id"], self.state["properties"]["schema_id"]["const"])
        self.assertEqual(self.event["$id"], self.event["properties"]["schema_id"]["const"])

    def test_manifest_binds_canonical_bytes_graph_dependency_and_mirror(self):
        self.assertEqual("sagekit-runtime-state-contract", self.manifest["contract_family"])
        self.assertEqual("v1", self.manifest["version"])
        self.assertEqual(1, self.manifest["manifest_version"])
        self.assertEqual({"state_schema", "event_schema"}, set(self.manifest["resources"]))
        for key, name in (("state_schema", "state.schema.json"), ("event_schema", "event.schema.json")):
            resource = self.manifest["resources"][key]
            self.assertEqual(name, resource["resource"])
            self.assertEqual(sha256(self.canonical[name]), resource["canonical_sha256"])
            self.assertRegex(resource["canonical_sha256"], r"^[0-9a-f]{64}$")
        dependency = self.manifest["dependencies"]["graph_contract_v1"]
        self.assertEqual("urn:sagekit:graph-contract:v1", dependency["contract_id"])
        self.assertEqual("docs/contracts/graph/v1/contract.json", dependency["contract_resource"])
        self.assertEqual(GRAPH_RESOURCE_DIGESTS["contract.json"], dependency["canonical_contract_sha256"])
        graph_manifest = load_json(REPOSITORY / dependency["contract_resource"])
        self.assertEqual(
            graph_manifest["resources"]["graph_schema"]["canonical_sha256"],
            dependency["canonical_resource_integrity"]["graph_schema_sha256"],
        )
        self.assertEqual(
            graph_manifest["resources"]["node_result_schema"]["canonical_sha256"],
            dependency["canonical_resource_integrity"]["node_result_schema_sha256"],
        )
        self.assertIn("canonical resource bytes", self.manifest["digest_semantics"])
        self.assertIn("not a runtime snapshot digest", self.manifest["digest_semantics"])
        self.assertEqual("sagekit/resources/contracts/runtime-state/v1", self.manifest["packaged_mirror"]["path"])
        self.assertIn("byte-identical", self.manifest["packaged_mirror"]["expectation"])

    def test_state_required_fields_statuses_and_graph_boundary_are_exact(self):
        self.assertEqual(STATE_REQUIRED, set(self.state["required"]))
        self.assertEqual(
            STATE_REQUIRED | {"handoff_ref", "recovery_status"},
            set(self.state["properties"]),
        )
        self.assertEqual(RUN_STATUSES, set(self.state["properties"]["run_status"]["enum"]))
        node = self.state["$defs"]["node_state"]
        self.assertEqual(NODE_STATE_REQUIRED, set(node["required"]))
        self.assertEqual(
            NODE_STATE_REQUIRED | {"result_digest", "blocker_reason"},
            set(node["properties"]),
        )
        self.assertEqual(NODE_STATUSES, set(node["properties"]["status"]["enum"]))
        self.assertNotIn("graph", self.state["properties"])
        self.assertEqual("#/$defs/sha256", self.state["properties"]["graph_digest"]["$ref"])
        self.assertIn("Stage 2B", node["properties"]["status"]["description"])
        self.assertNotIn("allowed_transitions", json.dumps(self.state).lower())

    def test_event_required_fields_types_and_status_facts_are_exact(self):
        self.assertEqual(EVENT_REQUIRED, set(self.event["required"]))
        self.assertEqual(
            EVENT_REQUIRED
            | {
                "node_id",
                "attempt_id",
                "previous_status",
                "next_status",
                "result_digest",
                "duration_ms",
            },
            set(self.event["properties"]),
        )
        self.assertEqual(EVENT_TYPES, set(self.event["properties"]["event_type"]["enum"]))
        self.assertEqual(NODE_STATUSES, set(self.event["properties"]["previous_status"]["enum"]))
        self.assertEqual(NODE_STATUSES, set(self.event["properties"]["next_status"]["enum"]))
        self.assertIn("Stage 2B", self.event["properties"]["next_status"]["description"])
        self.assertNotIn("allowed_transitions", json.dumps(self.event).lower())

    def test_valid_minimal_state_and_event_pass_the_declared_boundaries(self):
        self.assertTrue(is_schema_valid(valid_state(), self.state))
        self.assertTrue(is_schema_valid(valid_event(), self.event))

    def test_node_id_has_its_own_graph_compatible_opaque_string_definition(self):
        state_node_ref = self.state["$defs"]["node_state"]["properties"]["node_id"]["$ref"]
        event_node_ref = self.event["properties"]["node_id"]["$ref"]
        self.assertEqual("#/$defs/node_id", state_node_ref)
        self.assertEqual("#/$defs/node_id", event_node_ref)
        for schema in (self.state, self.event):
            node_id = schema["$defs"]["node_id"]
            self.assertEqual("string", node_id["type"])
            self.assertEqual(1, node_id["minLength"])
            self.assertNotIn("maxLength", node_id)
            self.assertNotIn("pattern", node_id)

        opaque_values = (
            "node with spaces",
            "path/segment\\opaque",
            "節点-α",
            "!leading-punctuation",
            "x" * 300,
        )
        for value in opaque_values:
            with self.subTest(value=value[:40]):
                state = valid_state()
                state["node_states"][0]["node_id"] = value
                event = valid_event()
                event.update({"event_type": "NODE_READY", "node_id": value})
                self.assertTrue(is_schema_valid(state, self.state))
                self.assertTrue(is_schema_valid(event, self.event))

        state = valid_state()
        state["node_states"][0]["node_id"] = ""
        event = valid_event()
        event.update({"event_type": "NODE_READY", "node_id": ""})
        self.assertFalse(is_schema_valid(state, self.state))
        self.assertFalse(is_schema_valid(event, self.event))

    def test_integer_fields_reject_bool_and_out_of_range_values(self):
        for field in ("graph_generation", "revision", "last_event_sequence"):
            payload = valid_state()
            payload[field] = True
            self.assertFalse(is_schema_valid(payload, self.state), field)
        payload = valid_state()
        payload["node_states"][0]["last_event_sequence"] = True
        self.assertFalse(is_schema_valid(payload, self.state))
        payload = valid_event()
        payload["sequence"] = True
        self.assertFalse(is_schema_valid(payload, self.event))
        payload["sequence"] = 0
        self.assertFalse(is_schema_valid(payload, self.event))
        payload = valid_state()
        payload["revision"] = -1
        self.assertFalse(is_schema_valid(payload, self.state))

    def test_attempt_identity_is_run_node_scoped_without_granting_authority(self):
        pending = valid_state()
        self.assertTrue(is_schema_valid(pending, self.state))
        running = valid_state()
        running["node_states"][0]["status"] = "RUNNING"
        self.assertFalse(is_schema_valid(running, self.state))
        running["node_states"][0]["attempt_id"] = "attempt:run-node-1"
        self.assertTrue(is_schema_valid(running, self.state))
        started = valid_event()
        started.update({"event_type": "NODE_STARTED", "node_id": "node:contract"})
        self.assertFalse(is_schema_valid(started, self.event))
        started["attempt_id"] = "attempt:run-node-1"
        self.assertTrue(is_schema_valid(started, self.event))
        attempt_description = self.event["properties"]["attempt_id"]["description"].lower()
        for phrase in ("run_id", "node_id", "does not grant"):
            self.assertIn(phrase, attempt_description)

    def test_event_trace_conditionals_require_bounded_observable_context(self):
        transitioned = valid_event()
        transitioned.update({"event_type": "NODE_TRANSITIONED", "node_id": "node:contract"})
        self.assertFalse(is_schema_valid(transitioned, self.event))
        transitioned.update({"previous_status": "READY", "next_status": "RUNNING"})
        self.assertTrue(is_schema_valid(transitioned, self.event))
        result = valid_event()
        result.update(
            {
                "event_type": "NODE_RESULT_RECORDED",
                "node_id": "node:contract",
                "attempt_id": "attempt:run-node-1",
            }
        )
        self.assertFalse(is_schema_valid(result, self.event))
        result["result_digest"] = "result:sha256:opaque"
        self.assertTrue(is_schema_valid(result, self.event))

    def test_every_object_is_closed_and_forbidden_payloads_are_rejected(self):
        for name, schema in (("state", self.state), ("event", self.event)):
            objects = list(object_schemas(schema))
            self.assertTrue(objects, name)
            for object_schema in objects:
                self.assertIs(False, object_schema.get("additionalProperties"), object_schema)
        self.assertTrue(FORBIDDEN_PROPERTIES.isdisjoint(property_names((self.state, self.event))))
        for forbidden in FORBIDDEN_PROPERTIES:
            payload = valid_event()
            payload[forbidden] = "not allowed"
            self.assertFalse(is_schema_valid(payload, self.event), forbidden)
        payload = valid_state()
        payload["graph"] = {}
        self.assertFalse(is_schema_valid(payload, self.state))

    def test_all_strings_and_arrays_are_bounded_and_refs_are_unique(self):
        for schema in (self.state, self.event):
            for item in walk(schema):
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "string" and "const" not in item and "enum" not in item:
                    if item is not schema["$defs"].get("node_id"):
                        self.assertIn("maxLength", item, item)
                if item.get("type") == "array":
                    self.assertIn("maxItems", item, item)
        for schema, names in (
            (self.state, ("evidence_refs",)),
            (self.event, ("evidence_refs", "artifact_refs")),
        ):
            for name in names:
                ref_array = schema["properties"].get(name) or schema["$defs"]["node_state"]["properties"][name]
                self.assertIs(True, ref_array["uniqueItems"])
        duplicate_refs = valid_event()
        duplicate_refs["evidence_refs"] = ["evidence:E1", "evidence:E1"]
        self.assertFalse(is_schema_valid(duplicate_refs, self.event))
        long_reason = valid_event()
        long_reason["reason_code"] = "R" * 129
        self.assertFalse(is_schema_valid(long_reason, self.event))

    def test_identity_contract_is_stable_repository_neutral_and_algorithm_deferred(self):
        identity = self.manifest["identity_contract"]
        run_text = identity["run_id"].lower()
        for phrase in ("authority", "graph identity", "stage 3b", "absolute path", "credential", "account", "hostname"):
            self.assertIn(phrase, run_text)
        event_text = identity["event_id"].lower()
        for phrase in ("run_id", "sequence", "random uuid", "timestamp", "stage 3b"):
            self.assertIn(phrase, event_text)
        attempt_text = identity["attempt_id"].lower()
        for phrase in ("run_id", "node_id", "does not grant", "stage 3b"):
            self.assertIn(phrase, attempt_text)
        serialized = json.dumps((self.manifest, self.state, self.event), sort_keys=True)
        self.assertNotRegex(
            serialized,
            re.compile(r"(?:^|[\"'])[A-Za-z]:[\\/]|(?:^|[\"'])/(?:Users|home|tmp)/"),
        )
        self.assertNotRegex(serialized, re.compile(r"(?i)(?:password|api[_-]?key|token)\s*[=:]\s*\S+"))

    def test_observed_timing_is_metadata_not_identity_authority_or_success(self):
        observed = self.event["properties"]["observed_at"]
        self.assertEqual("date-time", observed["format"])
        observed_text = observed["description"].lower()
        for phrase in ("observable metadata", "not semantic graph identity", "not event identity", "authority", "transition"):
            self.assertIn(phrase, observed_text)
        duration_text = self.event["properties"]["duration_ms"]["description"].lower()
        self.assertIn("not success evidence", duration_text)
        invalid = valid_event()
        invalid["observed_at"] = "2026-07-23T12:00:00"
        self.assertFalse(is_schema_valid(invalid, self.event))
        invalid["observed_at"] = "not-a-time"
        self.assertFalse(is_schema_valid(invalid, self.event))

    def test_memory_tiers_own_only_run_state_and_reference_other_tiers(self):
        boundary = self.manifest["memory_tier_boundary"]
        self.assertEqual("run state", boundary["owned_tier"])
        self.assertEqual(
            {"mode": "reference-only", "target": "configured ACTIVE_CONTEXT"},
            boundary["session_handoff"],
        )
        self.assertEqual("reference-only", boundary["project_memory"]["mode"])
        self.assertEqual(
            ["Profile", "Design", "decisions", "Closeout"],
            boundary["project_memory"]["targets"],
        )
        constraint = boundary["constraint"].lower()
        for phrase in ("must not copy", "must not modify", "accepted history", "milestone", "phase"):
            self.assertIn(phrase, constraint)
        self.assertIn("handoff_ref", self.state["properties"])
        self.assertNotIn("handoff_ref", self.event["properties"])

    def test_schema_presence_is_inert_and_graph_schema_is_not_copied(self):
        required_phrases = (
            "does not create .sagekit",
            "does not write runtime files",
            "does not acquire a lock or lease",
            "does not start a scheduler",
            "does not recover a run",
            "does not modify active_context",
            "does not modify project history",
            "does not execute a graph",
        )
        for schema in (self.state, self.event):
            description = schema["description"].lower()
            for phrase in required_phrases:
                self.assertIn(phrase, description)
            for item in walk(schema):
                if isinstance(item, dict) and "$ref" in item:
                    self.assertTrue(item["$ref"].startswith("#/$defs/"))
        copied_graph_fields = {
            "nodes",
            "joins",
            "source_authority",
            "governance_level",
            "autonomy_level",
            "human_gates",
        }
        self.assertTrue(copied_graph_fields.isdisjoint(property_names((self.state, self.event))))
        graph_snapshot = self.manifest["graph_snapshot"]
        self.assertEqual("urn:sagekit:graph-contract:v1", graph_snapshot["contract_id"])
        self.assertIn("Stage 2B canonical graph digest", graph_snapshot["semantic_identity"])
        self.assertIn("must not modify", graph_snapshot["payload_rule"])
        self.assertIn("does not grant authority", graph_snapshot["authority_boundary"])
        self.assertFalse((REPOSITORY / ".sagekit").exists())

    def test_only_frozen_paths_one_canonical_family_and_one_packaged_mirror_exist(self):
        self.assertEqual(EXPECTED_STAGE3D_PATHS, changed_paths_since_baseline())
        canonical_families = {
            path.parent.relative_to(REPOSITORY).as_posix()
            for path in (REPOSITORY / "docs").rglob("runtime-state/v1/contract.json")
        }
        packaged_families = {
            path.parent.relative_to(REPOSITORY).as_posix()
            for path in (REPOSITORY / "sagekit/resources").rglob("runtime-state/v1/contract.json")
        }
        self.assertEqual({"docs/contracts/runtime-state/v1"}, canonical_families)
        self.assertEqual({"sagekit/resources/contracts/runtime-state/v1"}, packaged_families)

    def test_stage2_resources_and_capability_boundaries_are_unchanged(self):
        graph_root = REPOSITORY / "docs/contracts/graph/v1"
        packaged_graph_root = REPOSITORY / "sagekit/resources/contracts/graph/v1"
        for name, expected_digest in GRAPH_RESOURCE_DIGESTS.items():
            self.assertEqual(expected_digest, sha256(graph_root / name))
            self.assertEqual((graph_root / name).read_bytes(), (packaged_graph_root / name).read_bytes())
        graph_manifest = load_json(graph_root / "contract.json")
        graph_schema = load_json(graph_root / "graph.schema.json")
        self.assertIn("Light remains graph-artifact optional", graph_manifest["compatibility"])
        self.assertIn("Light governance remains graph-artifact optional", graph_schema["description"])
        compatibility = self.manifest["compatibility"]
        self.assertIn("Stage 2B pure validator", compatibility)
        self.assertIn("Light and Graph optionality are unchanged", compatibility)


if __name__ == "__main__":
    unittest.main()
