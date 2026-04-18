import json
import subprocess
import shutil
from pathlib import Path


def evaluate(state: dict, policies_dir: str = "policies") -> list[dict]:
    """Run OPA evaluation against all policies and return violations."""
    opa_bin = shutil.which("opa")
    if not opa_bin:
        raise RuntimeError(
            "OPA binary not found. Install from https://www.openpolicyagent.org/docs/latest/#running-opa"
        )

    policies_path = Path(policies_dir)
    if not policies_path.exists():
        raise FileNotFoundError(f"Policies directory not found: {policies_dir}")

    state_json = json.dumps(state)
    violations = []

    for policy_file in sorted(policies_path.glob("*.rego")):
        package_name = _extract_package(policy_file)
        query = f"data.{package_name}.violation"

        result = subprocess.run(
            [opa_bin, "eval", "-d", str(policy_file), "-i", "/dev/stdin", query, "--format", "json"],
            input=state_json,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  ⚠️  OPA error on {policy_file.name}: {result.stderr.strip()}")
            continue

        output = json.loads(result.stdout)
        policy_violations = _extract_violations(output, policy_file.name)
        violations.extend(policy_violations)

    return violations


def _extract_package(policy_file: Path) -> str:
    """Extract the package name from a Rego file."""
    with open(policy_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("package "):
                return line.split("package ", 1)[1].strip()
    return policy_file.stem


def _extract_violations(opa_output: dict, policy_name: str) -> list[dict]:
    """Parse OPA JSON output and return flat list of violation dicts."""
    violations = []
    for result in opa_output.get("result", []):
        expressions = result.get("expressions", [])
        for expr in expressions:
            value = expr.get("value", [])
            if isinstance(value, list):
                for v in value:
                    v["policy"] = policy_name
                    violations.append(v)
            elif isinstance(value, set):
                for v in value:
                    if isinstance(v, dict):
                        v["policy"] = policy_name
                        violations.append(v)
    return violations
