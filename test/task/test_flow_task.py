from typing import List
from zrb.task.cmd_task import CmdTask
from zrb.task.task import Task
from zrb.task.flow_task import FlowTask
from zrb.task.decorator import python_task


def test_flow_task():
    flow_task = FlowTask(
        name='flow_task',
        steps=[
            [
                CmdTask(name='create-sodium', cmd='echo "Na"'),
                CmdTask(name='create-chlorine', cmd='echo "Cl"'),
            ],
            Task(
                name='create-salt',
                run=lambda *args, **kwargs: "NaCl"
            ),
            FlowTask(
                name='create-saline-water',
                steps=[
                    Task(
                        name='create-water',
                        run=lambda *args, **kwargs: "H2O + NaCl"
                    )
                ]
            )
        ]
    )
    function = flow_task.to_function()
    is_error: bool = False
    try:
        function()
    except Exception:
        is_error = True
    assert not is_error


def test_flow_task_with_existing_tasks():
    outputs: List[str] = []

    @python_task(
        name='prepare-lab'
    )
    def prepare_lab(*args, **kwargs):
        outputs.append('Lab prepared')

    @python_task(
        name='create-sodium'
    )
    def create_sodium(*args, **kwargs):
        outputs.append('Na')

    @python_task(
        name='create-chlorine'
    )
    def create_chlorine(*args, **kwargs):
        outputs.append('Cl')

    @python_task(
        name='create-salt'
    )
    def create_salt(*args, **kwargs):
        outputs.append('NaCl')

    flow_task = FlowTask(
        name='flow_task',
        upstreams=[prepare_lab],
        steps=[
            [
                create_sodium,
                create_chlorine
            ],
            create_salt
        ]
    )
    function = flow_task.to_function()
    function()
    assert outputs[0] == 'Lab prepared'
    assert 'Na' in outputs
    assert 'Cl' in outputs
    assert outputs[3] == 'NaCl'
