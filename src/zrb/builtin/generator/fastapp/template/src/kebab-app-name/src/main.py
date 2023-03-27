from component.app import app
from component.app_state import app_state
from component.log import logger
from component.messagebus import consumer, publisher
from config import app_name, app_enable_message_consumer
from helper.async_task import create_task

app_state.set_liveness(True)
messages = []


async def on_error(exception: Exception):
    logger.critical(exception)
    app_state.set_readiness(False)


@app.on_event('startup')
async def startup_event():
    logger.info(f'{app_name} started')
    if app_enable_message_consumer:
        create_task(consumer.run(), on_error=on_error)
    app_state.set_readiness(True)


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
