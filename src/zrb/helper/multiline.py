import click

from zrb.helper.typecheck import typechecked


@typechecked
def edit(editor: str, mark_comment: str, text: str, extension: str = "txt") -> str:
    result = click.edit(
        text="\n".join([mark_comment, text]), editor=editor, extension=f".{extension}"
    )
    if result is None:
        result = text
    return "\n".join(result.split(mark_comment)).strip()
