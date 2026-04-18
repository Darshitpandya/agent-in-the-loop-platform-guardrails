package guardrails.tagging

required_tags := {"env", "team", "cost-centre", "service"}

violation contains msg if {
    some resource in input.resources
    existing := {tag | some tag in {t.key | some t in resource.tags}}
    missing := required_tags - existing
    count(missing) > 0
    msg := {
        "resource": resource.id,
        "type": resource.type,
        "violation": "missing_tags",
        "missing": sort(missing),
        "severity": "medium",
    }
}
