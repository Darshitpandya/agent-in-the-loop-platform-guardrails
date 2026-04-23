# Remediation: Replace the wildcard IAM policy (action: s3:*, resource: *) with a least-privilege policy scoped to specific S3 actions (e.g. s3:GetObject, s3:PutObject) and a payments-specific resource ARN (arn:aws:s3:::payments-*) to remediate iam_too_broad and iam_resource_wildcard violations.
# This file represents the change the agent would apply.
# In production, this would modify the actual terraform/iam.tf
