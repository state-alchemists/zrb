from collections import deque


class Xcom(deque):

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} {list(self)}>"

    def push_value(self, value):
        self.append(value)

    def pop_value(self):
        return self.popleft()

    def peek_value(self):
        if len(self) > 0:
            return self[0]
        else:
            raise IndexError("Xcom is empty")
