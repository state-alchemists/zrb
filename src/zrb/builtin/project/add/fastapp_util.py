from zrb.util.string.conversion import double_quote, to_snake_case


def get_zrb_init_import_code(old_code: str) -> str | None:
    code = "from zrb import load_file"
    if code in old_code:
        return None
    return code


def get_zrb_init_load_app_name_task(app: str) -> str:
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
