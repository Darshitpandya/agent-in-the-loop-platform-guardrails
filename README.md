# Agent-in-the-Loop: Platform Guardrail Enforcement

> **"Don't Audit Drift. Engineer It Away."**

An autonomous agent that continuously enforces platform guardrails by scanning deployed state, evaluating OPA policies, reasoning over drift with Amazon Bedrock, and surfacing remediation PRs — through the developer workflow you already own.

**PlatformCon 2026** — Darshit Pandya | Senior Principal Engineer – Platform @ Serko

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLATFORM POLICY LAYER                         │
│  OPA Policies (Rego) — machine-readable, version-controlled     │
│  "What does compliant look like?"                                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT-IN-THE-LOOP                              │
│                    (Platform Primitive)                           │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  SCAN    │───▶│ EVALUATE │───▶│  REASON  │───▶│ SURFACE  │  │
│  │ Deployed │    │ OPA      │    │ Bedrock  │    │ GitHub   │  │
│  │ state    │    │ pass/fail│    │ why +    │    │ PR API   │  │
│  │          │    │ (determ.)│    │ fix      │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
│  OpenTelemetry traces every step │ Operated with SLOs            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DEVELOPER WORKFLOW                             │
│  PR in the service repo → developer reviews → merges            │
│  Same workflow. Same review. No new tool. Human gate always.     │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principle

**OPA decides compliance. Bedrock decides remediation. Neither hallucinates in its lane.**

| Component | Role | Hallucination Risk |
|---|---|---|
| OPA (Rego) | "Is this resource compliant?" — pass/fail | None — deterministic |
| Amazon Bedrock | "Why did it drift? What's the fix?" — reasoning | Controlled — output constrained by Pydantic schema, validated before PR creation |
| GitHub PR | Surface remediation in developer workflow | None — deterministic |
| Human gate | Final approval — always required | None — human judgment |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [OPA binary](https://www.openpolicyagent.org/docs/latest/#running-opa) installed and on PATH
- GitHub personal access token with `repo` scope
- (Optional) AWS account with Amazon Bedrock access (Claude Sonnet enabled)

### Setup

```bash
git clone https://github.com/Darshitpandya/agent-in-the-loop-platform-guardrails.git
cd agent-in-the-loop-platform-guardrails

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your GITHUB_TOKEN and GITHUB_REPO
```

### Run (Dry-Run Mode — No AWS Required)

```bash
python agent/enforce.py --scan sample-data/deployed-state.json --dry-run
```

This uses hardcoded reasoning (no Bedrock call) but creates a **real GitHub PR** in your repo.

### Run (Real Bedrock Mode)

```bash
# Ensure AWS credentials and BEDROCK_MODEL_ID are set in .env
python agent/enforce.py --scan sample-data/deployed-state.json
```

### Run Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## What This Is

A **blueprint** for the Agent-in-the-Loop pattern — a working implementation you can fork, extend, and adapt to your platform.

- ✅ Working OPA policies (4 guardrails)
- ✅ Working agent pipeline (scan → evaluate → reason → PR)
- ✅ Real GitHub PR creation with deduplication
- ✅ OpenTelemetry tracing
- ✅ Dry-run mode (no AWS required)
- ✅ OPA policy unit tests

## What This Is NOT

This is **not a production deployment**. It's a working blueprint that demonstrates the pattern. Below is a step-by-step guide to adapt it for your production environment.

---

## Production Adoption Guide

### Step 1: Replace the Scanner with Real AWS API Calls

The blueprint reads from `sample-data/deployed-state.json`. In production, you need to scan real infrastructure.

**What to change:** `agent/scanner.py`

**Replace with something like:**

```python
import boto3

def scan_aws(region: str = "ap-southeast-2") -> dict:
    """Scan real AWS resources and return state in the same format."""
    ecs = boto3.client("ecs", region_name=region)
    ec2 = boto3.client("ec2", region_name=region)
    iam = boto3.client("iam")

    resources = []

    # Example: scan ECS services
    clusters = ecs.list_clusters()["clusterArns"]
    for cluster in clusters:
        services = ecs.list_services(cluster=cluster)["serviceArns"]
        for service_arn in services:
            detail = ecs.describe_services(cluster=cluster, services=[service_arn])["services"][0]
            task_def = ecs.describe_task_definition(
                taskDefinition=detail["taskDefinition"]
            )["taskDefinition"]

            resources.append({
                "id": detail["serviceName"],
                "type": "ecs_service",
                "tags": [{"key": t["key"], "value": t["value"]} for t in detail.get("tags", [])],
                "containers": [
                    {"name": c["name"], "image": c["image"]}
                    for c in task_def["containerDefinitions"]
                ],
                # Add IAM and secrets scanning as needed
            })

    return {"resources": resources}
```

**Then update `enforce.py`** to call `scan_aws()` instead of reading a JSON file when `--scan` is not provided.

### Step 2: Write Your Own OPA Policies

The 4 included policies (tagging, base images, IAM scope, secrets) are examples. Your guardrails will be different.

**How to add a policy:**

1. Create a new `.rego` file in `policies/`:

```rego
package guardrails.your_custom_policy

violation contains msg if {
    some resource in input.resources
    # Your compliance logic here
    msg := {
        "resource": resource.id,
        "violation": "your_violation_type",
        "detail": "Description of what's wrong",
        "severity": "medium",
    }
}
```

2. The agent automatically picks up all `*.rego` files in the policies directory. No code changes needed.

3. Add a test in `tests/test_policies.py` for your new policy.

### Step 3: Configure GitHub PR Creation for Your Repos

The blueprint creates PRs in the repo specified by `GITHUB_REPO` env var. In production, you likely want PRs in the **service's own repo**, not the agent's repo.

**What to change:** `agent/pr_creator.py`

Update the `create_pr` function to use the `repo` field from the deployed state:

```python
# Instead of:
repo_name = os.environ.get("GITHUB_REPO")

# Use the service's repo from the scan data:
repo_name = remediation.analyses[0].resource_repo  # e.g., "acme-org/payments-svc"
```

You'll also need to add a `resource_repo` field to the `DriftAnalysis` Pydantic model and populate it from the scanner.

### Step 4: Add Error Handling and Retries

The blueprint has no retry logic. Production needs resilience.

**Add to `bedrock_reasoner.py`:**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def _call_bedrock(violations, state):
    # existing Bedrock call
    ...
```

**Add to `pr_creator.py`:** Same retry pattern for GitHub API calls.

**Add `tenacity` to `requirements.txt`.**

### Step 5: Add Rate Limiting

Without rate limiting, the agent can create dozens of PRs in a single run. This causes alert fatigue.

**Recommended approach:**

```python
MAX_PRS_PER_RUN = 10

def enforce_with_limits(violations_by_resource):
    created = 0
    for resource_id, violations in violations_by_resource.items():
        if created >= MAX_PRS_PER_RUN:
            print(f"  ⚠️  Rate limit reached ({MAX_PRS_PER_RUN} PRs). Remaining deferred to next scan.")
            break
        # Check if an open PR already exists for this resource (deduplication)
        if has_open_pr(resource_id):
            continue
        create_pr(...)
        created += 1
```

### Step 6: Configure OpenTelemetry for Production

The blueprint exports traces to the console. Production needs a real backend.

**Set in `.env`:**

```
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-collector.example.com:4317
```

Compatible backends: Jaeger, Grafana Tempo, AWS X-Ray (via ADOT collector), Honeycomb, Datadog.

### Step 7: Scope IAM Permissions

The blueprint uses whatever AWS credentials are in your environment. Production needs a dedicated IAM role.

**Minimum IAM policy for the agent:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:ap-southeast-2::foundation-model/anthropic.claude-sonnet-4-6"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:ListClusters", "ecs:ListServices", "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition", "ecs:ListTagsForResource",
        "ec2:DescribeInstances", "ec2:DescribeTags",
        "iam:GetPolicy", "iam:GetPolicyVersion"
      ],
      "Resource": "*"
    }
  ]
}
```

**For GitHub Actions:** Use [OIDC federation](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) instead of storing AWS credentials as secrets.

### Step 8: Adjust the Schedule

The blueprint runs every 6 hours. Adjust based on your drift tolerance:

```yaml
# .github/workflows/enforce.yml
on:
  schedule:
    - cron: '0 */6 * * *'   # Every 6 hours (default)
    # - cron: '0 * * * *'   # Every hour (aggressive)
    # - cron: '0 8 * * 1-5' # Weekdays at 8 AM (business hours only)
```

---

### Production Checklist

- [ ] Scanner queries real AWS APIs (not sample JSON)
- [ ] OPA policies match your actual guardrails
- [ ] PRs created in service repos (not agent repo)
- [ ] Error handling + retries on Bedrock and GitHub API calls
- [ ] Rate limiting (max PRs per run + deduplication)
- [ ] OTLP exporter configured for your observability backend
- [ ] Dedicated IAM role with scoped permissions
- [ ] GitHub Actions uses OIDC federation (no stored AWS credentials)
- [ ] Schedule adjusted to your drift tolerance
- [ ] SLO targets defined and monitored

---

## Project Structure

```
├── agent/
│   ├── enforce.py              Main entry point (--scan, --dry-run)
│   ├── scanner.py              Reads deployed state (JSON file or AWS APIs)
│   ├── evaluator.py            Runs OPA eval against all policies
│   ├── bedrock_reasoner.py     Calls Bedrock via Instructor / Pydantic
│   ├── pr_creator.py           Creates GitHub PR with deduplication
│   └── telemetry.py            OpenTelemetry tracing
├── models/
│   └── __init__.py             Pydantic schemas (Violation, RemediationPR, etc.)
├── policies/
│   ├── tagging.rego            Required resource tags
│   ├── base_images.rego        Approved base image versions
│   ├── iam_scope.rego          IAM least-privilege checks
│   └── secrets.rego            No hardcoded secrets
├── sample-data/
│   └── deployed-state.json     Sample state with intentional violations
├── tests/
│   └── test_policies.py        OPA policy unit tests
├── .github/workflows/
│   └── enforce.yml             Scheduled every 6 hours
├── .env.example                Credential placeholders
├── requirements.txt            Pinned dependencies
└── README.md                   This file
```

---

## OPA Policies Included

| Policy | What It Checks | Severity |
|---|---|---|
| `tagging.rego` | Required tags: `env`, `team`, `cost-centre`, `service` | Medium |
| `base_images.rego` | Container images match approved versions | High |
| `iam_scope.rego` | No wildcard IAM actions or resources | High |
| `secrets.rego` | Secrets stored in a secrets manager, not env vars | Medium |

### Adding Your Own Policy

Create a new `.rego` file in `policies/`. The agent automatically picks up all `*.rego` files.

```rego
package guardrails.your_policy

violation[msg] {
    resource := input.resources[_]
    # Your compliance logic here
    msg := {
        "resource": resource.id,
        "violation": "your_violation_type",
        "severity": "medium"
    }
}
```

---

## SLO Template

Define these SLOs for your enforcement agent once deployed:

| SLO | Target | OTel Metric |
|---|---|---|
| Scan completion rate | 99.9% | `agent.scan.completed` / `agent.scan.scheduled` |
| False positive rate | < 5% | PRs closed as "not a real violation" / total PRs |
| Remediation latency (p95) | < 5 min | `agent.scan.duration_seconds` |
| Policy evaluation accuracy | 98% | OPA results matching manual review |

---

## The Human Gate

```rego
default requires_human_approval = true
# There is no override.
```

Every remediation PR requires a human merge. The agent **never** auto-merges. This is a platform contract, not a configuration option.

**Why:** During stress testing, a tag remediation on a Terraform-managed DynamoDB table triggered a `terraform plan` that wanted to replace the resource. In staging, that's a lesson. In production, that's data loss.

---

## License

MIT
