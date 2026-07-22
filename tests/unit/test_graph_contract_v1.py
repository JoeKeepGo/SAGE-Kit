import hashlib
import json
import re
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
CANONICAL = REPOSITORY / "docs/contracts/graph/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/graph/v1"
RESOURCE_NAMES = (
    "contract.json",
    "graph.schema.json",
    "node-result.schema.json",
)

PERMISSION_MODES = {
    "READ_ONLY_REVIEW",
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
}
JOIN_POLICIES = {
    "all-required",
    "required-plus-optional",
    "first-success",
    "manual-gate",
    "corrective-join",
}
NODE_STATES = {
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


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def object_schemas(value):
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield value
        for child in value.values():
            yield from object_schemas(child)
    elif isinstance(value, list):
        for child in value:
            yield from object_schemas(child)


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class GraphContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = {name: CANONICAL / name for name in RESOURCE_NAMES}
        cls.packaged = {name: PACKAGED / name for name in RESOURCE_NAMES}
        cls.manifest = load_json(cls.canonical["contract.json"])
        cls.graph = load_json(cls.canonical["graph.schema.json"])
        cls.result = load_json(cls.canonical["node-result.schema.json"])

    def test_canonical_and_packaged_resource_families_are_exact_and_identical(self):
        self.assertEqual(RESOURCE_NAMES, tuple(sorted(path.name for path in CANONICAL.iterdir())))
        self.assertEqual(RESOURCE_NAMES, tuple(sorted(path.name for path in PACKAGED.iterdir())))
        for name in RESOURCE_NAMES:
            self.assertTrue(self.canonical[name].is_file())
            self.assertTrue(self.packaged[name].is_file())
            self.assertEqual(self.canonical[name].read_bytes(), self.packaged[name].read_bytes())

    def test_resources_parse_and_use_stable_repository_neutral_identifiers(self):
        for path in (*self.canonical.values(), *self.packaged.values()):
            load_json(path)
        self.assertEqual("urn:sagekit:graph-contract:v1", self.manifest["contract_id"])
        self.assertEqual("urn:sagekit:graph-contract:v1:graph", self.graph["$id"])
        self.assertEqual("urn:sagekit:graph-contract:v1:node-result", self.result["$id"])
        self.assertEqual(1, self.graph["properties"]["schema_version"]["const"])
        self.assertEqual(1, self.result["properties"]["schema_version"]["const"])

    def test_graph_fields_and_enums_are_explicit(self):
        required = set(self.graph["required"])
        self.assertTrue(
            {
                "schema_id",
                "schema_version",
                "graph_id",
                "generation",
                "source_authority",
                "governance_level",
                "autonomy_level",
                "human_gates",
                "nodes",
                "joins",
            }.issubset(required)
        )
        self.assertEqual({"Light", "Standard", "Heavy"}, set(self.graph["properties"]["governance_level"]["enum"]))
        self.assertEqual({"turn-based", "goal-based"}, set(self.graph["properties"]["autonomy_level"]["enum"]))
        node = self.graph["$defs"]["node"]
        self.assertEqual(
            {"id", "role", "depends_on", "permission", "verifier", "output_contract", "resources", "classification"},
            set(node["required"]),
        )
        self.assertEqual({"required", "optional"}, set(node["properties"]["classification"]["enum"]))
        self.assertEqual(PERMISSION_MODES, set(node["properties"]["permission"]["enum"]))
        self.assertEqual(JOIN_POLICIES, set(self.graph["$defs"]["join"]["properties"]["policy"]["enum"]))

    def test_governance_autonomy_and_permission_are_independent(self):
        properties = self.graph["properties"]
        self.assertIn("governance_level", properties)
        self.assertIn("autonomy_level", properties)
        permission = self.graph["$defs"]["node"]["properties"]["permission"]
        self.assertIn("explicit", permission["description"].lower())
        self.assertIn("not inferred", permission["description"].lower())
        self.assertNotIn("governance_level", json.dumps(permission))
        autonomy_description = properties["autonomy_level"]["description"].lower()
        self.assertIn("does not grant continuation authority", autonomy_description)
        self.assertNotIn("time-based", properties["autonomy_level"]["enum"])
        self.assertNotIn("proactive", properties["autonomy_level"]["enum"])

    def test_join_policy_descriptions_preserve_safety_boundaries(self):
        policy = self.graph["$defs"]["join"]["properties"]["policy"]
        description = policy["description"].lower()
        for phrase in ("redundant", "equivalent", "read-only exploration"):
            self.assertIn(phrase, description)
        for phrase in ("authority", "safety", "approval", "validator", "acceptance", "required failure"):
            self.assertIn(phrase, description)
        self.assertIn("may not bypass", description)

    def test_node_result_envelope_and_state_semantics_are_explicit(self):
        required = set(self.result["required"])
        self.assertTrue(
            {
                "schema_id",
                "schema_version",
                "node_id",
                "status",
                "changed_paths",
                "evidence_refs",
                "findings",
                "authority_change",
                "proposed_next_nodes",
            }.issubset(required)
        )
        status = self.result["properties"]["status"]
        self.assertEqual(NODE_STATES, set(status["enum"]))
        status_description = status["description"]
        self.assertIn("DONE_WITH_CONCERNS", status_description)
        self.assertIn("cannot satisfy a required success join", status_description)
        self.assertIn("not mapped to SUCCEEDED, PASS, or WAIVED", status_description)
        authority = self.result["properties"]["authority_change"]["description"].lower()
        self.assertIn("higher-authority decision", authority)
        self.assertIn("does not modify authority", authority)

    def test_no_action_required_has_evidence_bound_conditional(self):
        conditionals = self.result["allOf"]
        no_action = next(
            rule
            for rule in conditionals
            if rule.get("if", {}).get("properties", {}).get("status", {}).get("const") == "NO_ACTION_REQUIRED"
        )
        self.assertEqual(["status"], no_action["if"]["required"])
        self.assertEqual(
            {"inspected_scope", "decision", "evidence_refs"},
            set(no_action["then"]["required"]),
        )
        self.assertEqual(1, self.result["properties"]["inspected_scope"]["minItems"])
        self.assertEqual(1, self.result["properties"]["decision"]["minLength"])
        self.assertEqual(1, no_action["then"]["properties"]["evidence_refs"]["minItems"])
        description = self.result["properties"]["status"]["description"]
        self.assertIn("NO_ACTION_REQUIRED is distinct from SUCCEEDED, PASS, and WAIVED", description)
        self.assertIn("Stage 2B", description)

    def test_every_object_schema_rejects_unspecified_properties(self):
        for name, schema in (("graph", self.graph), ("node-result", self.result)):
            objects = list(object_schemas(schema))
            self.assertTrue(objects, name)
            for object_schema in objects:
                self.assertIs(False, object_schema.get("additionalProperties"), object_schema)

    def test_manifest_binds_canonical_bytes_and_packaged_mirror_expectations(self):
        self.assertEqual("sagekit-graph-contract", self.manifest["contract_family"])
        self.assertEqual("v1", self.manifest["version"])
        resources = self.manifest["resources"]
        self.assertEqual({"graph_schema", "node_result_schema"}, set(resources))
        for key, name in (("graph_schema", "graph.schema.json"), ("node_result_schema", "node-result.schema.json")):
            self.assertEqual(name, resources[key]["resource"])
            digest = hashlib.sha256(self.canonical[name].read_bytes()).hexdigest()
            self.assertEqual(digest, resources[key]["canonical_sha256"])
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        mirror = self.manifest["packaged_mirror"]
        self.assertEqual("sagekit/resources/contracts/graph/v1", mirror["path"])
        self.assertIn("byte-identical", mirror["expectation"])
        self.assertIn("canonical resource bytes", self.manifest["digest_semantics"])
        self.assertIn("not a semantic graph digest", self.manifest["digest_semantics"])

    def test_schemas_are_portable_and_do_not_embed_runtime_or_sensitive_dependencies(self):
        schemas = (self.graph, self.result)
        serialized = json.dumps(schemas, sort_keys=True)
        self.assertNotRegex(serialized, re.compile(r"(?:^|[\\s\"'])[A-Za-z]:[\\\\/]|(?:^|[\\s\"'])/(?:Users|home|tmp)/"))
        property_names = {
            key.lower()
            for value in walk(schemas)
            if isinstance(value, dict)
            for key in value.get("properties", {})
        }
        self.assertTrue({"credential", "credentials", "password", "secret", "secrets"}.isdisjoint(property_names))
        for value in walk(schemas):
            if isinstance(value, dict) and "$ref" in value:
                self.assertFalse(value["$ref"].startswith(("http://", "https://")))
        graph_description = self.graph["description"].lower()
        for phrase in (
            "does not activate graph execution",
            "does not create runtime state",
            "does not create a scheduler",
            "does not modify active_context",
            "does not execute nodes",
            "does not change project authority",
            "light governance remains graph-artifact optional",
        ):
            self.assertIn(phrase, graph_description)
        result_description = self.result["description"].lower()
        for phrase in ("observable decisions", "evidence references", "bounded findings", "changed surface", "transition proposals"):
            self.assertIn(phrase, result_description)
        for phrase in ("private reasoning", "complete chat or tool transcripts", "secrets", "credentials"):
            self.assertIn(phrase, result_description)

    def test_manifest_states_compatibility_and_source_authority_without_activating_graph(self):
        source = self.manifest["source_authority"]
        self.assertEqual("SAGE-Kit rebuild Stage 2A", source["identity"])
        self.assertEqual("rebuild.md#stage-2-graph-contract-and-node-result", source["reference"])
        compatibility = self.manifest["compatibility"].lower()
        self.assertIn("language-neutral", compatibility)
        self.assertIn("light remains graph-artifact optional", compatibility)
        self.assertIn("does not activate graph execution", compatibility)


if __name__ == "__main__":
    unittest.main()
