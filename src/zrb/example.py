from .task import BaseTask, Session
import asyncio


class Task(BaseTask):
    pass


def create_dummy_process(name: str, delay: int):
    async def run_dummy_process(task: Task, session: Session):
        print(f"start {name}")
        await asyncio.sleep(delay)
        print(f"stop {name}")
        return name
    return run_dummy_process


a = Task(name="a", action=create_dummy_process("a", 1))
b = Task(
    name="b",
    action=create_dummy_process("b", 10),
    readiness_checks=[
        Task(name="check-b", action=create_dummy_process("check-b", 2))
    ]
)
c = Task(name="c", action=create_dummy_process("c", 1), upstreams=[a, b])
d = Task(name="d", action=create_dummy_process("d", 2), upstreams=[a, b, c])
e = Task(name="e", action=create_dummy_process("e", 3), upstreams=[a, b, c])
f = Task(name="f", action=create_dummy_process("f", 1), upstreams=[d, e])

result = f.run()
print(result)
