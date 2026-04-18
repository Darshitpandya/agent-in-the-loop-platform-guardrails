package guardrails.secrets

violation contains msg if {
    some resource in input.resources
    some secret in resource.secrets
    secret.source == "env_var"
    msg := {
        "resource": resource.id,
        "violation": "secret_not_managed",
        "secret_name": secret.name,
        "detail": "Secret stored as environment variable — migrate to a secrets manager",
        "severity": "medium",
    }
}
