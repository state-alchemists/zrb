import os

MESSAGE = os.getenv("APP_MESSAGE", "Hello, world!")
PORT = int(os.getenv("APP_PORT", "8000"))


async def app(scope, receive, send):
    assert scope["type"] == "http"

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"text/plain"],
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": bytes(MESSAGE, "utf-8"),
        }
    )
