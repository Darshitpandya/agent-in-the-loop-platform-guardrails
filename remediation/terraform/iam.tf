# Remediation: Replace IAM action s3:* with least-privilege actions [s3:GetObject, s3:PutObject] and replace wildcard resource * with scoped ARN arn:aws:s3:::payments-* (fixes iam_too_broad and iam_resource_wildcard). REVIEWER: verify actions and ARN pattern are complete and correct.
# This file represents the change the agent would apply.
# In production, this would modify the actual terraform/iam.tf
