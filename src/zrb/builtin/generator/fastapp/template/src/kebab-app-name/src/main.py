from component.app import app
from component.app_state import app_state
from component.messagebus import consumer, publisher

app_state.set_liveness(True)
messages = []


@consumer.register('coba')
async def handle_event(message):
    messages.append(message)
    print(messages)


@app.get('/api/get')
def handle_get():
    return messages


@app.get('/api/send')
async def handle_send():
    return await publisher.publish('coba', 'sesuatu')
