package guardrails.base_images

approved_images := {
    "python": "3.12-slim",
    "node": "22-alpine",
    "java": "21-slim",
}

violation contains msg if {
    some resource in input.resources
    some container in resource.containers
    parts := split(container.image, ":")
    count(parts) == 2
    language := parts[0]
    version := parts[1]
    approved_version := approved_images[language]
    approved_version != version
    msg := {
        "resource": resource.id,
        "container": container.name,
        "violation": "outdated_base_image",
        "current_image": container.image,
        "approved_version": sprintf("%s:%s", [language, approved_version]),
        "severity": "high",
    }
}
