from integration.rpc import rpc_caller
from module.auth.component import Authorizer, RPCAuthorizer

authorizer: Authorizer = RPCAuthorizer(
    rpc_caller=rpc_caller,
    is_admin_rpc_name="auth_user_is_admin",
    is_guest_rpc_name="auth_user_is_guest",
    is_user_authorized_rpc_name="auth_is_user_authorized",
)
