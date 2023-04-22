from typing import List, Optional
from module.auth.schema.permission import PermissionData
from module.auth.component.model.permission_model import permission_model


async def ensure_entity_permission(
    module_name: str,
    entity_name: str,
    action_names: Optional[List[str]] = None
):
    if action_names is None:
        action_names = ['get', 'get_by_id', 'insert', 'update', 'delete']
    for action_name in action_names:
        await permission_model.ensure_permission(PermissionData(
            name=f'{module_name}:{entity_name}:{action_name}',
            description=f'{module_name}:{entity_name}:{action_name}'
        ))


async def register_permission():
    await ensure_entity_permission(
        module_name='auth', entity_name='group'
    )
    await ensure_entity_permission(
        module_name='auth', entity_name='permission'
    )
    await ensure_entity_permission(
        module_name='auth', entity_name='user'
    )
