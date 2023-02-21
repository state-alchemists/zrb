import os

message = os.environ.get('MY_MESSAGE', 'Hello, world!')
print(message)
