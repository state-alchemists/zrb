from typing import Any


def activate_all_compose_profile(*args: Any, **kwargs: Any) -> str:
    compose_profile_str = ",".join(
        ["monitoring", "monolith", "microservices", "kafka", "rabbitmq"]
    )
    return f"export COMPOSE_PROFILES={compose_profile_str}"
