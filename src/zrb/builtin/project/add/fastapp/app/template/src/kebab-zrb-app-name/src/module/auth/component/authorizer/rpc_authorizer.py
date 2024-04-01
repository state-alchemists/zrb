from component.rpc import Caller
from module.auth.component.authorizer.authorizer import Authorizer


class RPCAuthorizer(Authorizer):
    def __init__(
        self,
        rpc_caller: Caller,
        is_admin_rpc_name: str,
        is_guest_rpc_name: str,
        is_user_authorized_rpc_name: str,
    ):
        self.rpc_caller = rpc_caller
        self.is_admin_rpc_name = is_admin_rpc_name
        self.is_guest_rpc_name = is_guest_rpc_name
        self.is_user_authorized_rpc_name = is_user_authorized_rpc_name

    async def is_admin(self, user_id: str) -> bool:
        return await self.rpc_caller.call(self.is_admin_rpc_name, user_id)

    async def is_guest(self, user_id: str) -> bool:
        return await self.rpc_caller.call(self.is_guest_rpc_name, user_id)

    async def is_having_permission(self, user_id: str, *permission_name: str) -> bool:
        permission_map = await self.rpc_caller.call(
            self.is_user_authorized_rpc_name,
            id=user_id,
            permission_name=permission_name,
        )
        for permission in permission_map:
            if not permission_map[permission]:
                return False
        return True
