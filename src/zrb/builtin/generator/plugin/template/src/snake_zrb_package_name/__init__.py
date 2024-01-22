from .task.example_task import ExampleTask


def main():
    task = ExampleTask(name="main")
    fn = task.to_function()
    fn()
