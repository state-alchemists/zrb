from zrb.task.flow_task import FlowNode, FlowTask


def test_flow_task():
    flow_task = FlowTask(
        name='flow_task',
        nodes=[
            [
                FlowNode(
                    name='create-sodium',
                    cmd='echo "Na'
                ),
                FlowNode(
                    name='create-clorine',
                    cmd='echo "Cl'
                ),
            ],
            FlowNode(
                name='create-salt',
                run=lambda *args, **kwargs: "NaCl"
            )
        ]
    )
    main_loop = flow_task.create_main_loop()
    is_error: bool = False
    try:
        main_loop()
    except Exception:
        is_error = True
    assert is_error
