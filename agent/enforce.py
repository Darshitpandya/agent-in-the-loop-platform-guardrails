#!/usr/bin/env python3
"""Agent-in-the-Loop: Continuous guardrail enforcement agent.

Usage:
    python agent/enforce.py --scan sample-data/deployed-state.json
    python agent/enforce.py --scan sample-data/deployed-state.json --dry-run
"""

import argparse
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.scanner import scan
from agent.evaluator import evaluate
from agent.bedrock_reasoner import reason
from agent.pr_creator import create_pr
from agent.telemetry import trace_scan


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Guardrail enforcement agent")
    parser.add_argument("--scan", required=True, help="Path to deployed state JSON file")
    parser.add_argument("--policies", default="policies", help="Path to OPA policies directory")
    parser.add_argument("--dry-run", action="store_true", help="Use hardcoded reasoning instead of Bedrock")
    args = parser.parse_args()

    scan_id = str(uuid.uuid4())[:8]
    print(f"\n🛡️  Guardrail Enforcement Agent (scan: {scan_id})")
    print(f"{'─' * 50}")

    # Step 1: Scan
    print(f"\nScanning deployed state: {args.scan}")
    state = scan(args.scan)
    resource_count = len(state.get("resources", []))
    print(f"├── Resources scanned: {resource_count}")

    # Step 2: Evaluate
    print(f"\nEvaluating OPA policies ({args.policies}/)...")
    violations = evaluate(state, args.policies)

    # Group violations by policy for display
    by_policy = {}
    for v in violations:
        policy = v.get("policy", "unknown")
        by_policy.setdefault(policy, []).append(v)

    policy_files = sorted(Path(args.policies).glob("*.rego"))
    for pf in policy_files:
        count = len(by_policy.get(pf.name, []))
        status = f"{count} violation{'s' if count != 1 else ''}" if count > 0 else "PASS"
        icon = "❌" if count > 0 else "✅"
        resources = ""
        if count > 0:
            affected = {v.get("resource", "unknown") for v in by_policy[pf.name]}
            resources = f" ({', '.join(sorted(affected))})"
        print(f"├── {pf.name}: {icon} {status}{resources}")

    print(f"\nViolations found: {len(violations)}")
    compliant = resource_count - len({v.get("resource") for v in violations})
    print(f"Compliant: {compliant}/{resource_count} services")

    if not violations:
        print("\n✅ All resources compliant. No action needed.")
        trace_scan(scan_id, resource_count, 0, None)
        return

    # Step 3: Reason
    mode = "dry-run (hardcoded)" if args.dry_run else "Amazon Bedrock"
    print(f"\nReasoning via {mode}...")
    remediation = reason(violations, state, dry_run=args.dry_run)

    if remediation is None:
        print("  No remediation generated.")
        trace_scan(scan_id, resource_count, len(violations), None)
        return

    print(f"├── Likely cause: {remediation.analyses[0].likely_cause}")
    print(f"├── Risk level: {remediation.risk_level}")
    print(f"├── Human approval required: {remediation.requires_human_approval}")

    # Step 4: Surface PR
    print(f"\nCreating remediation PR...")
    pr_url = create_pr(remediation)

    if pr_url:
        print(f"├── ✅ PR created: {pr_url}")
    else:
        print(f"├── ℹ️  PR not created (see above)")

    # Step 5: Trace
    trace_scan(scan_id, resource_count, len(violations), pr_url)

    print(f"\n{'─' * 50}")
    print(f"🛡️  Scan complete: {scan_id}")
    print(f"   Resources: {resource_count} | Violations: {len(violations)} | PR: {'created' if pr_url else 'skipped'}")


if __name__ == "__main__":
    main()
