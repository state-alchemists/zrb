import os

message = os.getenv('MY_MESSAGE', 'Hello, world!')
post_message_1 = os.getenv('POST_MESSAGE_1', '')
post_message_2 = os.getenv('POST_MESSAGE_2', '')

print(message)
if post_message_1 != '':
    print(post_message_1)
if post_message_2 != '':
    print(post_message_2)
