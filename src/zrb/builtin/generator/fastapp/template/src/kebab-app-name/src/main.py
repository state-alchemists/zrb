from component.app import app
from component.app_state import app_state
from component.messagebus import consumer, publisher
from component.rpc import rpc_caller, rpc_server

app_state.set_liveness(True)
messages = []


@consumer.register('coba')
async def handle_event(message):
    messages.append(message)
    print(messages)


@rpc_server.register('add')
async def add(a: int, b: int):
    return a + b


@app.get('/api/get')
def handle_get():
    return messages


@app.get('/api/send')
async def handle_send():
    await publisher.publish('coba', 'sesuatu')
    result = await rpc_caller.call('add', 4, 5)
    return result
