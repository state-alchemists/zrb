from module.auth.core import Authorizer, RPCAuthorizer
from component.rpc import rpc_caller

authorizer: Authorizer = RPCAuthorizer(
    rpc_caller=rpc_caller,
    is_admin_rpc_name='auth_user_is_admin',
    is_guest_rpc_name='auth_user_is_guest',
    is_having_permission_rpc_name='auth_user_is_having_permission'
)
