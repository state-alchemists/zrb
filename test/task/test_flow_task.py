from typing import List
from zrb.task.flow_task import FlowNode, FlowTask
from zrb.task.decorator import python_task


def test_flow_task():
    flow_task = FlowTask(
        name='flow_task',
        nodes=[
            [
                FlowNode(name='create-sodium', cmd='echo "Na"'),
                FlowNode(name='create-chlorine', cmd='echo "Cl"'),
            ],
            FlowNode(
                name='create-salt',
                run=lambda *args, **kwargs: "NaCl"
            ),
            FlowNode(
                name='create-saline-water',
                nodes=[
                    FlowNode(
                        name='create-water',
                        run=lambda *args, **kwargs: "H2O + NaCl"
                    )
                ]
            )
        ]
    )
    main_loop = flow_task.create_main_loop()
    is_error: bool = False
    try:
        main_loop()
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
        nodes=[
            [
                FlowNode(task=create_sodium),
                FlowNode(task=create_chlorine)
            ],
            FlowNode(task=create_salt)
        ]
    )
    main_loop = flow_task.create_main_loop()
    main_loop()
    assert outputs[0] == 'Lab prepared'
    assert outputs[3] == 'NaCl'

