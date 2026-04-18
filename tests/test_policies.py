"""OPA policy unit tests. Requires OPA binary installed."""

import json
import subprocess
import shutil
import pytest

OPA = shutil.which("opa")
pytestmark = pytest.mark.skipif(OPA is None, reason="OPA binary not found")

COMPLIANT_RESOURCE = {
    "resources": [{
        "id": "orders-svc",
        "type": "ecs_service",
        "tags": [
            {"key": "team", "value": "commerce"},
            {"key": "env", "value": "prod"},
            {"key": "cost-centre", "value": "cc-200"},
            {"key": "service", "value": "orders-svc"},
        ],
        "containers": [{"name": "app", "image": "python:3.12-slim"}],
        "iam_policy": {"effect": "Allow", "action": ["s3:GetObject"], "resource": "arn:aws:s3:::orders-*"},
        "secrets": [{"name": "API_KEY", "source": "secrets_manager"}],
    }]
}

VIOLATING_RESOURCE = {
    "resources": [{
        "id": "payments-svc",
        "type": "ecs_service",
        "tags": [{"key": "team", "value": "payments"}],
        "containers": [{"name": "app", "image": "python:3.10-slim"}],
        "iam_policy": {"effect": "Allow", "action": ["s3:*"], "resource": "*"},
        "secrets": [{"name": "DB_PASSWORD", "source": "env_var"}],
    }]
}


def _eval_policy(policy_file: str, input_data: dict) -> list:
    """Run OPA eval and return violations."""
    with open(policy_file) as f:
        for line in f:
            if line.strip().startswith("package "):
                package = line.strip().split("package ", 1)[1]
                break

    result = subprocess.run(
        [OPA, "eval", "-d", policy_file, "-i", "/dev/stdin", f"data.{package}.violation", "--format", "json"],
        input=json.dumps(input_data),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    violations = []
    for r in output.get("result", []):
        for expr in r.get("expressions", []):
            val = expr.get("value", [])
            if isinstance(val, list):
                violations.extend(val)
    return violations


class TestTaggingPolicy:
    def test_compliant_resource_passes(self):
        violations = _eval_policy("policies/tagging.rego", COMPLIANT_RESOURCE)
        assert len(violations) == 0

    def test_missing_tags_detected(self):
        violations = _eval_policy("policies/tagging.rego", VIOLATING_RESOURCE)
        assert len(violations) == 1
        assert set(violations[0]["missing"]) == {"env", "cost-centre", "service"}


class TestBaseImagesPolicy:
    def test_approved_image_passes(self):
        violations = _eval_policy("policies/base_images.rego", COMPLIANT_RESOURCE)
        assert len(violations) == 0

    def test_outdated_image_detected(self):
        violations = _eval_policy("policies/base_images.rego", VIOLATING_RESOURCE)
        assert len(violations) == 1
        assert violations[0]["current_image"] == "python:3.10-slim"


class TestIamScopePolicy:
    def test_scoped_policy_passes(self):
        violations = _eval_policy("policies/iam_scope.rego", COMPLIANT_RESOURCE)
        assert len(violations) == 0

    def test_wildcard_detected(self):
        violations = _eval_policy("policies/iam_scope.rego", VIOLATING_RESOURCE)
        assert len(violations) >= 1


class TestSecretsPolicy:
    def test_managed_secret_passes(self):
        violations = _eval_policy("policies/secrets.rego", COMPLIANT_RESOURCE)
        assert len(violations) == 0

    def test_env_var_secret_detected(self):
        violations = _eval_policy("policies/secrets.rego", VIOLATING_RESOURCE)
        assert len(violations) == 1
        assert violations[0]["secret_name"] == "DB_PASSWORD"
