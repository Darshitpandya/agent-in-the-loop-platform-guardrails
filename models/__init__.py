from __future__ import annotations

from pydantic import BaseModel, Field


class Violation(BaseModel):
    resource: str
    violation: str
    severity: str
    detail: str = ""


class DriftAnalysis(BaseModel):
    resource_id: str
    violations: list[Violation]
    likely_cause: str = Field(description="Why this drift likely happened")
    remediation_summary: str = Field(description="One-line summary of the fix")


class FileChange(BaseModel):
    path: str = Field(description="File path to change, e.g. terraform/tags.tf")
    description: str = Field(description="What the change does")


class RemediationPR(BaseModel):
    title: str = Field(description="PR title, e.g. 'Guardrail remediation: payments-svc'")
    body: str = Field(description="PR body with violations, likely cause, and fix summary")
    analyses: list[DriftAnalysis]
    files_changed: list[FileChange]
    risk_level: str = Field(description="low, medium, or high")
    requires_human_approval: bool = Field(default=True)
