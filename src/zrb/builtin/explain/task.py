import os
from zrb.task.wiki_task import create_wiki_tasks
from zrb.builtin.explain._group import explain_group
from zrb.runner import runner


CURRENT_DIRECTORY = os.path.dirname(__file__)

explain_tasks = create_wiki_tasks(
    directory=os.path.join(CURRENT_DIRECTORY, "explanation"),
    group=explain_group,
    runner=runner
)
