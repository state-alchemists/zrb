from typing import List, Optional

from module.auth.integration.model.permission_model import permission_model
from module.auth.schema.permission import PermissionData

DEFAULT_ACTION_NAMES = ["get", "get_by_id", "insert", "update", "delete"]
ACTION_DESCRIPTION = {
    "get": "list all",
    "get_by_id": "get single",
    "insert": "insert new",
    "update": "update",
    "delete": "delete",
}


async def ensure_entity_permission(
    module_name: str, entity_name: str, action_names: Optional[List[str]] = None
):
    if action_names is None:
        action_names = DEFAULT_ACTION_NAMES
    for action_name in action_names:
        caption = ACTION_DESCRIPTION[action_name]
        await permission_model.ensure_permission(
            PermissionData(
                name=f"{module_name}:{entity_name}:{action_name}",
                description=f"Allow {caption} {entity_name} on {module_name}",
            )
        )


async def register_permission():
    await ensure_entity_permission(module_name="auth", entity_name="group")
    await ensure_entity_permission(module_name="auth", entity_name="permission")
    await ensure_entity_permission(module_name="auth", entity_name="user")
    await ensure_entity_permission(
        module_name="log", entity_name="activity", action_names=["get", "get_by_id"]
    )
