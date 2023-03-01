import os

message = os.getenv('MY_MESSAGE', 'Hello, world!')
print(message)
