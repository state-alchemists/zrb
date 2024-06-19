from zrb.helper.typecheck import typechecked
import click


@typechecked
def edit(editor: str, mark_comment: str, text: str) -> str:
    result = click.edit(text="\n".join([mark_comment, text]), editor=editor)
    if result is None:
        result = text
    return "\n".join(result.split(mark_comment)).strip()
