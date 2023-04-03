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
    logger.info('🥪 Registering API for "snake_module_name"')

    @app.get('/api/v1/kebab-module-name')
    async def get_snake_module_name():
        # Publish hit event
        await publisher.publish(
            'hit_snake_module_name', '/api/v1/kebab-module-name'
        )
        # Send RPC request
        result = await rpc_caller.call(
            'process_snake_module_name', 'hello', 'world', magic_number=42
        )
        return result
