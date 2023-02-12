from zrb.helper.util import (
    coalesce, to_camel_case, to_pascal_case, to_kebab_case,
    to_snake_case, to_human_readable
)


def test_coalesce():
    assert coalesce('a', 'b', 'c') == 'a'
    assert coalesce(None, 'b', 'c') == 'b'
    assert coalesce(None, None, 'c') == 'c'
    assert coalesce(None, None, None) is None


def test_to_camel_case():
    assert to_camel_case('') == ''
    assert to_camel_case(' send  RPC  Request ') == 'sendRpcRequest'
    assert to_camel_case('send RPC Request') == 'sendRpcRequest'
    assert to_camel_case('sendRPCRequest') == 'sendRpcRequest'
    assert to_camel_case('SendRPCRequest') == 'sendRpcRequest'
    assert to_camel_case('send-rpc-request') == 'sendRpcRequest'
    assert to_camel_case('send_rpc_request') == 'sendRpcRequest'
    assert to_camel_case('send_rpc_request!!!') == 'sendRpcRequest'


def test_to_pascal_case():
    assert to_pascal_case('') == ''
    assert to_pascal_case(' send  RPC  Request ') == 'SendRpcRequest'
    assert to_pascal_case('send RPC Request') == 'SendRpcRequest'
    assert to_pascal_case('sendRPCRequest') == 'SendRpcRequest'
    assert to_pascal_case('SendRPCRequest') == 'SendRpcRequest'
    assert to_pascal_case('send-rpc-request') == 'SendRpcRequest'
    assert to_pascal_case('send_rpc_request') == 'SendRpcRequest'
    assert to_pascal_case('send_rpc_request!!!') == 'SendRpcRequest'


def test_to_kebab_case():
    assert to_kebab_case('') == ''
    assert to_kebab_case(' send  RPC  Request ') == 'send-rpc-request'
    assert to_kebab_case('send RPC Request') == 'send-rpc-request'
    assert to_kebab_case('sendRPCRequest') == 'send-rpc-request'
    assert to_kebab_case('SendRPCRequest') == 'send-rpc-request'
    assert to_kebab_case('send-rpc-request') == 'send-rpc-request'
    assert to_kebab_case('send_rpc_request') == 'send-rpc-request'
    assert to_kebab_case('send_rpc_request!!!') == 'send-rpc-request'


def test_to_snake_case():
    assert to_snake_case('') == ''
    assert to_snake_case(' send  RPC  Request ') == 'send_rpc_request'
    assert to_snake_case('send RPC Request') == 'send_rpc_request'
    assert to_snake_case('sendRPCRequest') == 'send_rpc_request'
    assert to_snake_case('SendRPCRequest') == 'send_rpc_request'
    assert to_snake_case('send-rpc-request') == 'send_rpc_request'
    assert to_snake_case('send_rpc_request') == 'send_rpc_request'
    assert to_snake_case('send_rpc_request!!!') == 'send_rpc_request'


def test_to_human_readable():
    assert to_human_readable('') == ''
    assert to_human_readable(' send  RPC  Request ') == 'send RPC Request'
    assert to_human_readable('send RPC Request') == 'send RPC Request'
    assert to_human_readable('sendRPCRequest') == 'send RPC Request'
    assert to_human_readable('SendRPCRequest') == 'Send RPC Request'
    assert to_human_readable('send-rpc-request') == 'send rpc request'
    assert to_human_readable('send_rpc_request') == 'send rpc request'
    assert to_human_readable('send_rpc_request!!!') == 'send rpc request!!!'

