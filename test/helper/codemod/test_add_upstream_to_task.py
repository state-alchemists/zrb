from zrb.helper.codemod.add_upstream_to_task import add_upstream_to_task


task_with_upstream_code = '''
a = Task(name='alpha', upstreams=[])
b = Task(name='beta', upstreams=[a])
c = Task(name='gamma', upstreams=[b])
'''

new_task_with_upstream_code = '''
a = Task(name='alpha', upstreams=[])
b = Task(name='beta', upstreams=[a, delta])
c = Task(name='gamma', upstreams=[b])
'''


def test_add_upstream_to_task_with_upstream():
    code = add_upstream_to_task(
        task_with_upstream_code, 'beta', 'delta'
    )
    assert code == new_task_with_upstream_code


task_without_upstream_code = '''
a = Task(name='alpha')
b = Task(name='beta')
c = Task(name='gamma')
'''

new_task_without_upstream_code = '''
a = Task(name='alpha')
b = Task(name='beta', upstreams = [delta])
c = Task(name='gamma')
'''


def test_add_upstream_to_task_without_upstream():
    code = add_upstream_to_task(
        task_without_upstream_code, 'beta', 'delta'
    )
    assert code == new_task_without_upstream_code
