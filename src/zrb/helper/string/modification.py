from zrb.helper.typecheck import typechecked


@typechecked
def double_quote(text: str) -> str:
    return '"' + text.replace('"', '\\"') + '"'
