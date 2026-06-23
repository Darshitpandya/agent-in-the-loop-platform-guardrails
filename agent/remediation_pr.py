import os

from github import Github, GithubException
from models import RemediationPR


def create_pr(remediation: RemediationPR) -> str | None:
    """Create a GitHub PR from a RemediationPR. Returns the PR URL or None."""
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPO")

    if not token or not repo_name:
        print("  ⚠️  GITHUB_TOKEN or GITHUB_REPO not set — skipping PR creation.")
        print(f"  📋 PR that would be created:\n     Title: {remediation.title}")
        return None

    gh = Github(token)
    repo = gh.get_repo(repo_name)

    # Create a branch for the remediation
    default_branch = repo.default_branch
    ref = repo.get_git_ref(f"heads/{default_branch}")
    branch_name = f"guardrail-remediation/{remediation.analyses[0].resource_id}"

    try:
        repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)
    except GithubException as e:
        if e.status == 422:  # Branch already exists — deduplication
            print(f"  ℹ️  Branch {branch_name} already exists — skipping (deduplication).")
            return None
        raise

    # Create placeholder files showing the remediation
    for file_change in remediation.files_changed:
        try:
            repo.create_file(
                path=f"remediation/{file_change.path}",
                message=f"🛡️ {file_change.description}",
                content=f"# Remediation: {file_change.description}\n# This file represents the change the agent would apply.\n# In production, this would modify the actual {file_change.path}\n",
                branch=branch_name,
            )
        except GithubException as e:
            if e.status != 422:  # 422 = file already exists
                raise

    # Create the PR
    pr = repo.create_pull(
        title=remediation.title,
        body=remediation.body,
        head=branch_name,
        base=default_branch,
    )

    labels = ["agent-remediation", f"risk-{remediation.risk_level}"]
    for label_name in labels:
        try:
            repo.get_label(label_name)
        except GithubException:
            repo.create_label(label_name, color="d73a4a" if "high" in label_name else "e4e669")
        pr.add_to_labels(label_name)

    return pr.html_url
