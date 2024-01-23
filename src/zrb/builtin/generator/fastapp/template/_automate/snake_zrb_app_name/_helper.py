from typing import Any, List

from zrb import Task

###############################################################################
# Functions
###############################################################################


def should_start_local_microservices(*args: Any, **kwargs: Any) -> bool:
    if not kwargs.get("local_snake_zrb_app_name", True):
        return False
    run_mode = kwargs.get("snake_zrb_app_name_run_mode", "monolith")
    return run_mode == "microservices"


def get_support_container_compose_profiles(*args: Any, **kwargs: Any) -> List[str]:
    task: Task = kwargs.get("_task")
    env_map = task.get_env_map()
    compose_profiles: List[str] = []
    broker_type = env_map.get("APP_BROKER_TYPE", "rabbitmq")
    if broker_type in ["rabbitmq", "kafka"]:
        compose_profiles.append(broker_type)
    if kwargs.get("enable_snake_zrb_app_name_monitoring", False):
        compose_profiles.append("monitoring")
    return compose_profiles


def get_container_compose_profiles(*args: Any, **kwargs: Any) -> str:
    compose_profiles = get_support_container_compose_profiles(*args, **kwargs)
    compose_profiles.append(
        kwargs.get("snake_zrb_app_name_run_mode", "monolith"),
    )
    return compose_profiles


def activate_support_compose_profile(*args: Any, **kwargs: Any) -> str:
    compose_profiles = get_support_container_compose_profiles(*args, **kwargs)
    compose_profile_str = ",".join(compose_profiles)
    return f"export COMPOSE_PROFILES={compose_profile_str}"


def should_start_support_container(*args: Any, **kwargs: Any) -> bool:
    if not kwargs.get("local_snake_zrb_app_name", True):
        return False
    compose_profiles = get_support_container_compose_profiles(*args, **kwargs)
    return len(compose_profiles) > 0


def should_start_local_monolith(*args: Any, **kwargs: Any) -> bool:
    if not kwargs.get("local_snake_zrb_app_name", True):
        return False
    return kwargs.get("snake_zrb_app_name_run_mode", "monolith") == "monolith"


def activate_selected_compose_profile(*args: Any, **kwargs: Any) -> str:
    compose_profiles = get_container_compose_profiles(*args, **kwargs)
    compose_profile_str = ",".join(compose_profiles)
    return f"export COMPOSE_PROFILES={compose_profile_str}"


def activate_all_compose_profile(*args: Any, **kwargs: Any) -> str:
    compose_profile_str = ",".join(
        ["monitoring", "monolith", "microservices", "kafka", "rabbitmq"]
    )
    return f"export COMPOSE_PROFILES={compose_profile_str}"


def should_start_container(*args: Any, **kwargs: Any) -> bool:
    return kwargs.get("local_snake_zrb_app_name", True)
