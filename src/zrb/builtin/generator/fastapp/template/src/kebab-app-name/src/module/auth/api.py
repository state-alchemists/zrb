from fastapi import FastAPI
from logging import Logger
from core.messagebus.messagebus import Publisher
from core.rpc.rpc import Caller


def register_api(
    logger: Logger,
    app: FastAPI,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Registering API for "auth"')

    @app.get('/api/v1/auth')
    async def get_auth():
        # Publish hit event
        await publisher.publish(
            'hit_auth', '/api/v1/auth'
        )
        # Send RPC request
        result = await rpc_caller.call(
            'process_auth', 'hello', 'world', magic_number=42
        )
        return result
