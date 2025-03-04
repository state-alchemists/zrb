import os

from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import double_quote, to_snake_case


def is_in_project_app_dir(ctx: AnyContext, file_path: str) -> bool:
    return file_path.startswith(
        os.path.abspath(
            os.path.join(ctx.input.project_dir, to_snake_case(ctx.input.app))
        )
    )


def is_project_zrb_init_file(ctx: AnyContext, file_path: str) -> bool:
    return file_path == os.path.abspath(
        os.path.join(ctx.input.project_dir, "zrb_init.py")
    )


def update_project_zrb_init_file(ctx: AnyContext, zrb_init_path: str):
    existing_zrb_init_code = read_file(zrb_init_path)
    write_file(
        file_path=zrb_init_path,
        content=[
            _get_import_load_file_code(existing_zrb_init_code),
            existing_zrb_init_code.strip(),
            _get_load_app_name_task_code(ctx.input.app),
        ],
    )


def _get_import_load_file_code(existing_code: str) -> str | None:
    code = "from zrb import load_file"
    return code if code not in existing_code else None


def _get_load_app_name_task_code(app: str) -> str:
    snake_app_name = to_snake_case(app)
    load_file_param = ", ".join(
        [double_quote(part) for part in [snake_app_name, "_zrb", "task.py"]]
    )
    return "\n".join(
        [
            f"# Load {app} automation",
            f"{snake_app_name} = load_file(os.path.join(_DIR, {load_file_param}))",
            f"assert {snake_app_name}",
        ]
    )
