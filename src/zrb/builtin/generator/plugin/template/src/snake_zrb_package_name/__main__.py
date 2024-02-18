from .task.example_task import ExampleTask

assert ExampleTask


def main():
    fn = ExampleTask.to_function()
    fn()
