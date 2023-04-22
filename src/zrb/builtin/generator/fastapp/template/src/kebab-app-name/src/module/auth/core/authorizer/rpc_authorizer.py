from module.auth.core.authorizer.authorizer import Authorizer
from core.rpc import Caller


class RPCAuthorizer(Authorizer):

    def __init__(
        self,
        rpc_caller: Caller,
        is_admin_rpc_name: str,
        is_guest_rpc_name: str,
        is_having_permission_rpc_name: str,
    ):
        self.rpc_caller = rpc_caller
        self.is_admin_rpc_name = is_admin_rpc_name
        self.is_guest_rpc_name = is_guest_rpc_name
        self.is_having_permission_rpc_name = is_having_permission_rpc_name

    async def is_admin(self, user_id: str) -> bool:
        return await self.rpc_caller.call(
            self.is_admin_rpc_name, user_id
        )

    async def is_guest(self, user_id: str) -> bool:
        return await self.rpc_caller.call(
            self.is_guest_rpc_name, user_id
        )

    async def is_having_permission(
        self, user_id: str, permission_name
    ) -> bool:
        return await self.rpc_caller.call(
            self.is_having_permission_rpc_name, user_id, permission_name
        )
