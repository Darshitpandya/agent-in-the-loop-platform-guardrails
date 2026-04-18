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

| Component | Role | Deterministic? |
|---|---|---|
| OPA (Rego) | "Is this resource compliant?" — pass/fail | ✅ Yes |
| Amazon Bedrock | "Why did it drift? What's the fix?" — reasoning | ❌ No (constrained by Pydantic schema) |
| GitHub PR | Surface remediation in developer workflow | ✅ Yes |
| Human gate | Final approval — always required | ✅ Yes |

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

This is **not a production deployment**. To use in your production environment, you need to:

| What to Change | Why | How |
|---|---|---|
| Replace `scanner.py` | Currently reads a JSON file. Production needs real AWS API calls. | Use `boto3` to describe ECS services, EC2 instances, IAM policies, etc. |
| Add your own OPA policies | The 4 included policies are examples. Your guardrails are different. | Write Rego policies for your specific compliance requirements. |
| Add error handling + retries | The blueprint has no retry logic. | Add exponential backoff on Bedrock and GitHub API calls. |
| Add rate limiting | The blueprint creates PRs without throttling. | Add max PRs per hour / per service to avoid PR floods. |
| Configure OTLP exporter | Console exporter is for demo. Production needs a real backend. | Set `OTEL_EXPORTER_OTLP_ENDPOINT` to your collector (Jaeger, Grafana, etc.). |
| Scope Bedrock IAM permissions | The blueprint uses broad credentials. | Create a dedicated IAM role with `bedrock:InvokeModel` only. |

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
