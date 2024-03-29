import os

from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable
from zrb.task.task import Task


@typechecked
def write_config(
    template_file: str, config_file: str, remove_old_config: bool = False
) -> Callable[..., Any]:
    async def set_config(*args, **kwargs):
        task: Task = kwargs.get("_task")
        rendered_config_file = os.path.expandvars(
            os.path.expanduser(task.render_str(config_file))
        )
        rendered_template_file = os.path.expandvars(
            os.path.expanduser(task.render_str(template_file))
        )
        if remove_old_config and os.path.exists(rendered_config_file):
            task.print_out(f"Removing {rendered_config_file}")
            os.remove(rendered_config_file)
        additional_content = await read_text_file_async(rendered_template_file)
        content = ""
        if os.path.exists(rendered_config_file):
            content = await read_text_file_async(rendered_config_file) + "\n"
        new_content = content + additional_content
        task.print_out(f"Writing content to {rendered_config_file}")
        await write_text_file_async(rendered_config_file, new_content)

    return set_config
