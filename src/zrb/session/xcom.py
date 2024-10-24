from collections import deque


class Xcom(deque):
    def push(self, value):
        self.append(value)

    def get(self):
        return self.popleft()

    def peek(self):
        if len(self) > 0:
            return self[0]
        else:
            raise IndexError("Xcom is empty")
