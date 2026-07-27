import copy
import hashlib
import json
import unittest
from pathlib import Path

from sagekit.graph_contract import canonical_graph_digest
from sagekit.graph_evolution_contract import (
    GRAPH_EVOLUTION_OPERATIONS,
    STAGE5_LINEAGE_CONTRACT_SHA256,
    GraphEvolutionContractError,
    canonical_graph_evolution_digest,
    validate_graph_evolution_acceptance,
    validate_graph_evolution_document,
    validate_graph_evolution_error,
    validate_graph_evolution_outcome,
    validate_graph_evolution_preauthorization,
    validate_graph_evolution_proposal,
    validate_graph_evolution_request,
    validate_graph_evolution_result,
)


REPOSITORY = Path(__file__).resolve().parents[2]
CANONICAL = REPOSITORY / "docs/contracts/graph-evolution/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/graph-evolution/v1"
RESOURCE_NAMES = (
    "contract.json",
    "request.schema.json",
    "preauthorization.schema.json",
    "proposal.schema.json",
    "acceptance.schema.json",
    "result.schema.json",
    "error.schema.json",
)
OPERATIONS = {
    "ADD_CORRECTIVE",
    "ADD_VERIFICATION",
    "ADD_INVESTIGATION",
    "SPLIT_PENDING",
    "DISABLE_OPTIONAL_PENDING",
    "NO_CHANGE",
}
CHANGE_CLASSES = {"C0", "C1", "C2", "C3"}
PERMISSIONS = {
    "READ_ONLY_REVIEW",
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
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
    "scheduler",
    "database",
}
DOMAINS = {
    "request": b"sagekit-graph-evolution-request-v1\0",
    "preauthorization": b"sagekit-graph-evolution-preauthorization-v1\0",
    "proposal": b"sagekit-graph-evolution-proposal-v1\0",
    "acceptance": b"sagekit-graph-evolution-acceptance-v1\0",
    "result": b"sagekit-graph-evolution-result-v1\0",
    "error": b"sagekit-graph-evolution-error-v1\0",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_resource_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def minimal_graph(generation=8):
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph/spec",
        "generation": generation,
        "source_authority": {
            "identity": "pm/rebuild",
            "reference": "authority/stage6",
        },
        "governance_level": "Heavy",
        "autonomy_level": "turn-based",
        "human_gates": ["acceptance"],
        "nodes": [
            {
                "id": "node/verify",
                "role": "Verifier",
                "depends_on": [],
                "permission": "READ_ONLY_REVIEW",
                "verifier": "verifier/focused",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": [],
                "classification": "required",
            }
        ],
        "joins": [],
    }


def authority():
    return {
        "authority_id": "pm/rebuild",
        "authority_role": "PROJECT_MANAGER",
        "authority_ref": "authority/stage6",
    }


def proposer():
    return {
        "node_id": "node/controller",
        "role": "Controller",
        "permission": "WRITE_AUTHORIZED",
    }


def request(operation="ADD_VERIFICATION"):
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:request",
        "schema_version": 1,
        "request_id": "request/verify-001",
        "operation": operation,
        "graph_id": "graph/spec",
        "parent_generation": 7,
        "parent_graph_digest": "a" * 64,
        "authority": authority(),
        "proposer": proposer(),
        "node_id": "node/verify",
        "change_class": "C1",
        "reason_code": "VERIFICATION_GAP",
        "evidence_refs": ["evidence/stage5/failure-001"],
        "decision_refs": ["decision/review-001"],
        "affected_paths": ["sagekit/graph_contract.py"],
        "stage5_lineage_digest": "b" * 64,
    }


def preauthorization():
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:preauthorization",
        "schema_version": 1,
        "preauthorization_id": "preauth/stage6-001",
        "graph_id": "graph/spec",
        "parent_generation": 7,
        "parent_graph_digest": "a" * 64,
        "authority": authority(),
        "allowed_operations": [
            "ADD_CORRECTIVE",
            "ADD_VERIFICATION",
            "ADD_INVESTIGATION",
            "SPLIT_PENDING",
            "DISABLE_OPTIONAL_PENDING",
            "NO_CHANGE",
        ],
        "allowed_change_classes": ["C0", "C1"],
        "allowed_node_ids": ["node/controller", "node/verify"],
        "allowed_roles": ["Controller", "Verifier"],
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


def proposal(operation="ADD_VERIFICATION"):
    value = request(operation)
    value["schema_id"] = "urn:sagekit:graph-evolution:v1:proposal"
    value["proposal_id"] = "proposal/verify-001"
    value["request_digest"] = canonical_graph_evolution_digest(
        "request", request(operation)
    )
    value["preauthorization_digest"] = canonical_graph_evolution_digest(
        "preauthorization", preauthorization()
    )
    if operation == "NO_CHANGE":
        return value
    target_graph = minimal_graph()
    value.update(
        {
            "target_generation": 8,
            "target_graph": target_graph,
            "target_graph_digest": canonical_graph_digest(target_graph),
        }
    )
    return value


def acceptance(decision="ACCEPTED", operation="ADD_VERIFICATION"):
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:acceptance",
        "schema_version": 1,
        "acceptance_id": "acceptance/verify-001",
        "proposal_digest": canonical_graph_evolution_digest(
            "proposal", proposal(operation)
        ),
        "preauthorization_digest": canonical_graph_evolution_digest(
            "preauthorization", preauthorization()
        ),
        "decision": decision,
        "authority": authority(),
        "evaluator": {
            "node_id": "node/verify",
            "role": "Verifier",
            "decision": "APPROVE" if decision == "ACCEPTED" else "REJECT",
            "decision_ref": "decision/evaluator-001",
        },
        "reason_code": (
            "WITHIN_PREAUTHORIZATION"
            if decision == "ACCEPTED"
            else "EVALUATOR_REJECTED"
        ),
        "decision_refs": ["decision/pm-001"],
    }


def result(operation="ADD_VERIFICATION", outcome="ACCEPTED"):
    value = {
        "schema_id": "urn:sagekit:graph-evolution:v1:result",
        "schema_version": 1,
        "request_digest": canonical_graph_evolution_digest(
            "request", request(operation)
        ),
        "preauthorization_digest": canonical_graph_evolution_digest(
            "preauthorization", preauthorization()
        ),
        "proposal_digest": canonical_graph_evolution_digest(
            "proposal", proposal(operation)
        ),
        "acceptance_digest": canonical_graph_evolution_digest(
            "acceptance", acceptance("ACCEPTED", operation)
        ),
        "operation": operation,
        "outcome": outcome,
        "graph_id": "graph/spec",
        "parent_generation": 7,
        "parent_graph_digest": "a" * 64,
        "message_code": (
            "NO_CHANGE_ACCEPTED"
            if operation == "NO_CHANGE"
            else "EVOLUTION_ACCEPTED"
        ),
    }
    if operation != "NO_CHANGE" and outcome == "ACCEPTED":
        graph = minimal_graph()
        value["target_generation"] = 8
        value["target_graph_digest"] = canonical_graph_digest(graph)
    return value


def error():
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:error",
        "schema_version": 1,
        "error_code": "INPUT_INVALID",
        "message_code": "STRICT_DOCUMENT_REQUIRED",
        "document_kind": "proposal",
        "issues": [
            {
                "location": "$.operation",
                "issue_code": "INVALID_OPERATION",
            }
        ],
    }


class GraphEvolutionContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(CANONICAL / "contract.json")
        cls.schemas = {
            name.removesuffix(".schema.json"): load_json(CANONICAL / name)
            for name in RESOURCE_NAMES
            if name.endswith(".schema.json")
        }

    def test_exact_resource_manifest_and_byte_identical_packaged_mirrors(self):
        self.assertEqual(set(RESOURCE_NAMES), {path.name for path in CANONICAL.iterdir()})
        self.assertEqual(set(RESOURCE_NAMES), {path.name for path in PACKAGED.iterdir()})
        self.assertEqual(
            set(RESOURCE_NAMES) - {"contract.json"},
            {entry["resource"] for entry in self.manifest["resources"].values()},
        )
        for name in RESOURCE_NAMES:
            canonical = CANONICAL / name
            packaged = PACKAGED / name
            self.assertEqual(canonical.read_bytes(), packaged.read_bytes(), name)
            if name == "contract.json":
                continue
            entry = next(
                item
                for item in self.manifest["resources"].values()
                if item["resource"] == name
            )
            self.assertEqual(canonical_resource_sha256(canonical), entry["canonical_sha256"])

    def test_dependencies_reuse_stage5_digest_and_graph_owner(self):
        dependencies = self.manifest["dependencies"]
        lineage_path = REPOSITORY / "docs/contracts/evidence-lineage/v1/contract.json"
        graph_contract = REPOSITORY / "docs/contracts/graph/v1/contract.json"
        graph_schema = REPOSITORY / "docs/contracts/graph/v1/graph.schema.json"
        self.assertEqual(
            canonical_resource_sha256(lineage_path),
            dependencies["evidence_lineage_contract_v1"]["canonical_sha256"],
        )
        self.assertEqual(
            STAGE5_LINEAGE_CONTRACT_SHA256,
            dependencies["evidence_lineage_contract_v1"]["canonical_sha256"],
        )
        self.assertEqual(
            canonical_resource_sha256(graph_contract),
            dependencies["graph_contract_v1"]["canonical_sha256"],
        )
        self.assertEqual(
            canonical_resource_sha256(graph_schema),
            dependencies["graph_schema_v1"]["canonical_sha256"],
        )
        self.assertIn("validate_graph_contract", dependencies["graph_contract_v1"]["relation"])
        self.assertIn("does not redefine", dependencies["graph_contract_v1"]["relation"])

    def test_six_operations_and_closed_preauthorization_allowlists_are_frozen(self):
        self.assertEqual(OPERATIONS, set(GRAPH_EVOLUTION_OPERATIONS))
        request_schema = self.schemas["request"]
        self.assertEqual(
            OPERATIONS,
            set(request_schema["$defs"]["operation"]["enum"]),
        )
        preauth = self.schemas["preauthorization"]
        self.assertEqual(
            OPERATIONS,
            set(preauth["properties"]["allowed_operations"]["items"]["enum"]),
        )
        self.assertEqual(
            CHANGE_CLASSES,
            set(preauth["properties"]["allowed_change_classes"]["items"]["enum"]),
        )
        self.assertEqual(
            PERMISSIONS,
            set(preauth["properties"]["allowed_permissions"]["items"]["enum"]),
        )
        self.assertFalse(preauth["additionalProperties"])
        self.assertFalse(preauth["properties"]["generation_budget"]["additionalProperties"])
        self.assertFalse(preauth["properties"]["evaluator"]["additionalProperties"])
        self.assertEqual(
            OPERATIONS,
            set(preauth["properties"]["operation_budgets"]["properties"]),
        )
        self.assertFalse(
            preauth["properties"]["operation_budgets"]["additionalProperties"]
        )

    def test_valid_documents_have_domain_separated_canonical_digests(self):
        values = {
            "request": request(),
            "preauthorization": preauthorization(),
            "proposal": proposal(),
            "acceptance": acceptance(),
            "result": result(),
            "error": error(),
        }
        validators = {
            "request": validate_graph_evolution_request,
            "preauthorization": validate_graph_evolution_preauthorization,
            "proposal": validate_graph_evolution_proposal,
            "acceptance": validate_graph_evolution_acceptance,
            "result": validate_graph_evolution_result,
            "error": validate_graph_evolution_error,
        }
        digests = set()
        for kind, value in values.items():
            with self.subTest(kind=kind):
                validation = validators[kind](value)
                self.assertTrue(validation.valid, validation.issues)
                expected = hashlib.sha256(
                    DOMAINS[kind] + canonical_bytes(value)
                ).hexdigest()
                self.assertEqual(expected, validation.digest)
                self.assertEqual(
                    expected,
                    canonical_graph_evolution_digest(kind, value),
                )
                self.assertEqual(
                    expected,
                    canonical_graph_evolution_digest(value),
                )
                self.assertTrue(
                    validate_graph_evolution_document(kind, value).valid
                )
                digests.add(expected)
        self.assertEqual(len(values), len(digests))

    def test_manifest_fixed_vector_matches_independent_request_digest(self):
        vector = self.manifest["canonical_digest"]["fixed_vectors"][0]
        self.assertEqual("request-001", vector["vector_id"])
        self.assertEqual(request(), vector["document"])
        expected = hashlib.sha256(
            DOMAINS["request"] + canonical_bytes(vector["document"])
        ).hexdigest()
        self.assertEqual(expected, vector["expected_sha256"])
        self.assertEqual(
            expected,
            canonical_graph_evolution_digest("request", vector["document"]),
        )

    def test_no_change_has_no_target_graph_or_generation(self):
        no_change = proposal("NO_CHANGE")
        self.assertTrue(validate_graph_evolution_proposal(no_change).valid)
        for forbidden in ("target_generation", "target_graph", "target_graph_digest"):
            self.assertNotIn(forbidden, no_change)
            invalid = copy.deepcopy(no_change)
            invalid[forbidden] = (
                minimal_graph() if forbidden == "target_graph" else 8
            )
            if forbidden == "target_graph_digest":
                invalid[forbidden] = "c" * 64
            self.assertFalse(validate_graph_evolution_proposal(invalid).valid)
        no_change_result = result("NO_CHANGE", "NO_CHANGE")
        self.assertTrue(validate_graph_evolution_result(no_change_result).valid)
        self.assertNotIn("target_generation", no_change_result)
        self.assertNotIn("target_graph_digest", no_change_result)

    def test_changed_proposal_requires_graph_owner_binding(self):
        value = proposal()
        self.assertTrue(validate_graph_evolution_proposal(value).valid)
        invalid_graph = copy.deepcopy(value)
        invalid_graph["target_graph"]["nodes"][0]["permission"] = "ROOT"
        validation = validate_graph_evolution_proposal(invalid_graph)
        self.assertFalse(validation.valid)
        self.assertIn("GRAPH_INVALID", {issue.issue_code for issue in validation.issues})
        wrong_digest = copy.deepcopy(value)
        wrong_digest["target_graph_digest"] = "f" * 64
        self.assertFalse(validate_graph_evolution_proposal(wrong_digest).valid)
        wrong_generation = copy.deepcopy(value)
        wrong_generation["target_generation"] = 9
        self.assertFalse(validate_graph_evolution_proposal(wrong_generation).valid)

    def test_strict_unknown_fields_duplicate_json_names_and_invalid_kind_fail(self):
        for validator, value in (
            (validate_graph_evolution_request, request()),
            (validate_graph_evolution_preauthorization, preauthorization()),
            (validate_graph_evolution_proposal, proposal()),
            (validate_graph_evolution_acceptance, acceptance()),
            (validate_graph_evolution_result, result()),
            (validate_graph_evolution_error, error()),
        ):
            invalid = copy.deepcopy(value)
            invalid["unexpected"] = True
            self.assertFalse(validator(invalid).valid)
        duplicate = (
            '{"schema_id":"urn:sagekit:graph-evolution:v1:request",'
            '"schema_id":"urn:sagekit:graph-evolution:v1:request"}'
        )
        self.assertFalse(validate_graph_evolution_request(duplicate).valid)
        with self.assertRaises(GraphEvolutionContractError):
            canonical_graph_evolution_digest("bogus", request())

    def test_preauthorization_is_bounded_and_fail_closed(self):
        self.assertTrue(
            validate_graph_evolution_preauthorization(preauthorization()).valid
        )
        cases = []
        duplicate_operation = preauthorization()
        duplicate_operation["allowed_operations"].append("NO_CHANGE")
        cases.append(duplicate_operation)
        unknown_budget = preauthorization()
        unknown_budget["operation_budgets"]["ROOT"] = 1
        cases.append(unknown_budget)
        unlisted_budget = preauthorization()
        unlisted_budget["allowed_operations"] = ["NO_CHANGE"]
        cases.append(unlisted_budget)
        invalid_role = preauthorization()
        invalid_role["authority"]["authority_role"] = "WORKER"
        cases.append(invalid_role)
        non_independent = preauthorization()
        non_independent["evaluator"]["independent"] = False
        cases.append(non_independent)
        for value in cases:
            self.assertFalse(
                validate_graph_evolution_preauthorization(value).valid,
                value,
            )

    def test_malformed_nested_allowlists_and_byte_overflow_return_issues(self):
        malformed = preauthorization()
        malformed["allowed_node_ids"] = None
        malformed["allowed_roles"] = None
        malformed["allowed_permissions"] = None
        validation = validate_graph_evolution_preauthorization(malformed)
        self.assertFalse(validation.valid)
        self.assertTrue(validation.issues)

        oversized = request()
        oversized["request_id"] = "x" * (1024 * 1024)
        validation = validate_graph_evolution_request(oversized)
        self.assertFalse(validation.valid)
        self.assertEqual(
            {"DOCUMENT_BYTE_BUDGET_EXCEEDED"},
            {issue.issue_code for issue in validation.issues},
        )

    def test_references_and_paths_reject_uri_absolute_and_newline_values(self):
        invalid_values = (
            "https://example.invalid/evidence",
            "file:///tmp/secret",
            "/etc/passwd",
            "\\\\server\\share",
            "C:\\secret.txt",
            "evidence/ok\nsecret",
        )
        for value in invalid_values:
            invalid_ref = request()
            invalid_ref["evidence_refs"] = [value]
            self.assertFalse(validate_graph_evolution_request(invalid_ref).valid)
            invalid_path = request()
            invalid_path["affected_paths"] = [value]
            self.assertFalse(validate_graph_evolution_request(invalid_path).valid)

    def test_privacy_forbidden_properties_are_absent_from_every_schema(self):
        for name, schema in self.schemas.items():
            property_names = {
                key
                for item in walk(schema)
                if isinstance(item, dict)
                for key in item.get("properties", {})
            }
            self.assertFalse(
                property_names.intersection(FORBIDDEN_PROPERTIES),
                (name, property_names.intersection(FORBIDDEN_PROPERTIES)),
            )
            self.assertIn("additionalProperties", schema)
            self.assertFalse(schema["additionalProperties"])

    def test_acceptance_is_evaluator_consistent_and_proposal_is_inert(self):
        accepted = acceptance()
        self.assertTrue(validate_graph_evolution_acceptance(accepted).valid)
        inconsistent = copy.deepcopy(accepted)
        inconsistent["evaluator"]["decision"] = "REJECT"
        self.assertFalse(validate_graph_evolution_acceptance(inconsistent).valid)
        boundaries = self.manifest["semantic_boundaries"]
        self.assertIn("does not grant", boundaries["proposal_inertness"])
        self.assertIn("does not execute", boundaries["proposal_inertness"])
        self.assertIn("host", boundaries["apply_ownership"])

    def test_result_and_error_are_exclusive(self):
        good_result = result()
        good_error = error()
        self.assertTrue(
            validate_graph_evolution_outcome(result=good_result).valid
        )
        self.assertTrue(
            validate_graph_evolution_outcome(error=good_error).valid
        )
        both = validate_graph_evolution_outcome(
            result=good_result,
            error=good_error,
        )
        neither = validate_graph_evolution_outcome()
        self.assertFalse(both.valid)
        self.assertFalse(neither.valid)
        self.assertEqual(
            {"RESULT_ERROR_EXCLUSIVITY"},
            {issue.issue_code for issue in both.issues},
        )
        self.assertEqual(
            {"RESULT_ERROR_EXCLUSIVITY"},
            {issue.issue_code for issue in neither.issues},
        )

    def test_module_does_not_construct_or_apply_proposals(self):
        import sagekit.graph_evolution_contract as module

        public = set(module.__all__)
        self.assertFalse(
            {
                "build_proposal",
                "create_proposal",
                "apply_proposal",
                "execute_proposal",
                "schedule_proposal",
            }.intersection(public)
        )
        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        for forbidden in (
            "subprocess",
            "sqlite",
            "scheduler",
            "stage7",
            "from .cli",
            "import cli",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
