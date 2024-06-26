from zrb.task.path_watcher import PathWatcher
from zrb.task.cmd_task import CmdTask
import os

_CURRENT_DIR = os.path.dirname(__file__)


def test_path_watcher():
    patch_watcher = PathWatcher(
        path=os.path.join(_CURRENT_DIR, 'resources', '**', "*.txt"),
        ignored_path=os.path.join(_CURRENT_DIR, 'resources', 'a'),
    )
    toucher = CmdTask(
        name='toucher',
        cwd=os.path.join(_CURRENT_DIR, 'resources'),
        cmd=[
            'touch a/a.txt',
            'sleep 1',
            'touch b/b.txt',
        ]
    )
    task = CmdTask(
        name='task',
        upstreams=[patch_watcher, toucher],
        cmd='echo {{task.get_xcom("watch-path.file")}}'
    )
    fn = task.to_function()
    result = fn()
    output = result.output
    assert output == os.path.join(_CURRENT_DIR, 'resources', 'b', 'b.txt')
