from zrb import BaseTask, StrInput, runner

task_1 = BaseTask(
    name='task-1',
    inputs=[
        StrInput(name='satu', shortcut='s', default='1', prompt='satu'),
        StrInput(name='dua', shortcut='d', default='2', prompt='dua'),
    ],
)

task_2 = BaseTask(
    name='task-2',
    inputs=[
        StrInput(name='tiga', shortcut='t', default='3', prompt='tiga'),
        StrInput(name='empat', shortcut='e', default='4', prompt='empat'),
    ],
    upstreams=[task_1]
)

runner.register(task_1)
runner.register(task_2)
