package guardrails.iam_scope

violation contains msg if {
    some resource in input.resources
    some action in resource.iam_policy.action
    endswith(action, ":*")
    msg := {
        "resource": resource.id,
        "violation": "iam_too_broad",
        "detail": sprintf("Wildcard action %s detected — use least-privilege actions", [action]),
        "severity": "high",
    }
}

violation contains msg if {
    some resource in input.resources
    resource.iam_policy.resource == "*"
    msg := {
        "resource": resource.id,
        "violation": "iam_resource_wildcard",
        "detail": "Wildcard resource * detected — scope to specific ARNs",
        "severity": "high",
    }
}
