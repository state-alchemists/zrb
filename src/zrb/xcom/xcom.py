from collections import deque


class Xcom(deque):

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} {list(self)}>"

    def push(self, value):
        self.append(value)

    def get(self):
        return self.popleft()

    def peek(self):
        if len(self) > 0:
            return self[0]
        else:
            raise IndexError("Xcom is empty")
