from component.app import app
from component.app_state import app_state
from component.log import logger
from component.messagebus import consumer, publisher
from helper.async_task import create_task

app_state.set_liveness(True)
messages = []


async def on_error(exception: Exception):
    logger.critical(exception)
    app_state.set_readiness(False)


@app.on_event('startup')
async def startup_event():
    logger.info('Started')
    create_task(consumer.run(), on_error=on_error)
    app_state.set_readiness(True)


@consumer.register('coba')
async def handle_event(message):
    messages.append(message)
    print(messages)


@app.get('/')
def handle_get():
    return ('hello world')


@app.get('/send')
async def handle_send():
    return await publisher.publish('coba', 'sesuatu')
