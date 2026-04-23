#!/usr/bin/env python3
"""Agent-in-the-Loop: Continuous guardrail enforcement agent.

Orchestrator — coordinates the agent pipeline:
  state_scanner.py → policy_evaluator.py → bedrock_reasoner.py → remediation_pr.py

Usage:
    python agent/orchestrator.py --scan sample-data/deployed-state.json
    python agent/orchestrator.py --scan sample-data/deployed-state.json --dry-run
"""

import argparse
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.state_scanner import scan
from agent.policy_evaluator import evaluate
from agent.bedrock_reasoner import reason
from agent.remediation_pr import create_pr
from agent.trace_emitter import trace_scan

# ANSI colour codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Guardrail enforcement agent")
    parser.add_argument("--scan", required=True, help="Path to deployed state JSON file")
    parser.add_argument("--policies", default="policies", help="Path to OPA policies directory")
    parser.add_argument("--dry-run", action="store_true", help="Use hardcoded reasoning instead of Bedrock")
    args = parser.parse_args()

    scan_id = str(uuid.uuid4())[:8]
    print(f"\n{BOLD}{GREEN}🛡️  Guardrail Enforcement Agent{RESET} {DIM}(scan: {scan_id}){RESET}")
    print(f"{GREEN}{'─' * 50}{RESET}")

    # Step 1: Scan
    print(f"\n{CYAN}Scanning deployed state:{RESET} {args.scan}")
    state = scan(args.scan)
    resource_count = len(state.get("resources", []))
    print(f"{GREEN}├──{RESET} Resources scanned: {BOLD}{resource_count}{RESET}")

    # Step 2: Evaluate
    print(f"\n{CYAN}Evaluating OPA policies{RESET} ({args.policies}/)...")
    violations = evaluate(state, args.policies)

    # Group violations by policy for display
    by_policy = {}
    for v in violations:
        policy = v.get("policy", "unknown")
        by_policy.setdefault(policy, []).append(v)

    policy_files = sorted(Path(args.policies).glob("*.rego"))
    for pf in policy_files:
        count = len(by_policy.get(pf.name, []))
        if count > 0:
            status = f"{RED}{count} violation{'s' if count != 1 else ''}{RESET}"
            icon = "❌"
            affected = {v.get("resource", "unknown") for v in by_policy[pf.name]}
            resources = f" {DIM}({', '.join(sorted(affected))}){RESET}"
        else:
            status = f"{GREEN}PASS{RESET}"
            icon = "✅"
            resources = ""
        print(f"{GREEN}├──{RESET} {pf.name}: {icon} {status}{resources}")

    print(f"\n{BOLD}Violations found: {RED}{len(violations)}{RESET}")
    compliant = resource_count - len({v.get("resource") for v in violations})
    print(f"Compliant: {GREEN}{compliant}/{resource_count}{RESET} services")

    if not violations:
        print(f"\n{GREEN}✅ All resources compliant. No action needed.{RESET}")
        trace_scan(scan_id, resource_count, 0, None)
        return

    # Step 3: Reason
    mode = "dry-run (hardcoded)" if args.dry_run else "Amazon Bedrock"
    print(f"\n{CYAN}Reasoning via {BOLD}{mode}{RESET}{CYAN}...{RESET}")
    remediation = reason(violations, state, dry_run=args.dry_run)

    if remediation is None:
        print("  No remediation generated.")
        trace_scan(scan_id, resource_count, len(violations), None)
        return

    print(f"{GREEN}├──{RESET} Likely cause: {remediation.analyses[0].likely_cause}")
    print(f"{GREEN}├──{RESET} Risk level: {YELLOW}{remediation.risk_level}{RESET}")
    print(f"{GREEN}├──{RESET} Human approval required: {BOLD}{remediation.requires_human_approval}{RESET}")

    # Step 4: Surface PR
    print(f"\n{CYAN}Creating remediation PR...{RESET}")
    pr_url = create_pr(remediation)

    if pr_url:
        print(f"{GREEN}├── ✅ PR created:{RESET} {BOLD}{pr_url}{RESET}")
    else:
        print(f"{YELLOW}├── ℹ️  PR not created (see above){RESET}")

    # Step 5: Trace
    trace_scan(scan_id, resource_count, len(violations), pr_url)

    print(f"\n{GREEN}{'─' * 50}{RESET}")
    print(f"{BOLD}{GREEN}🛡️  Scan complete:{RESET} {DIM}{scan_id}{RESET}")
    print(f"   Resources: {resource_count} | Violations: {RED}{len(violations)}{RESET} | PR: {GREEN}{'created' if pr_url else 'skipped'}{RESET}")


if __name__ == "__main__":
    main()
