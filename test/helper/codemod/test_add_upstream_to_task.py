from zrb.helper.codemod.add_upstream_to_task import add_upstream_to_task


def test_add_upstream_to_task_with_upstream():
    code = add_upstream_to_task(
        code='\n'.join([
            "a = Task(name='alpha', upstreams=[])",
            "b = Task(name='beta', upstreams=[a])",
            "c = Task(name='gamma', upstreams=[b])",
        ]),
        task_name='beta',
        upstream_task_name='delta'
    )
    assert code == '\n'.join([
        "a = Task(name='alpha', upstreams=[])",
        "b = Task(name='beta', upstreams=[a, delta])",
        "c = Task(name='gamma', upstreams=[b])",
    ])


def test_add_upstream_to_task_without_upstream():
    code = add_upstream_to_task(
        code='\n'.join([
            "a = Task(name='alpha')",
            "b = Task(name='beta')",
            "c = Task(name='gamma')",
        ]),
        task_name='beta',
        upstream_task_name='delta'
    )
    assert code == '\n'.join([
        "a = Task(name='alpha')",
        "b = Task(name='beta', upstreams = [delta])",
        "c = Task(name='gamma')",
    ])
