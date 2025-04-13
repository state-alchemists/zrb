import os

from zrb.context.any_shared_context import AnySharedContext
from zrb.input.str_input import StrInput
from zrb.util.file import read_file
from zrb.util.string.conversion import to_pascal_case


class PreviousSessionInput(StrInput):

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self.get_default_str(ctx)
        script = read_file(
            file_path=os.path.join(os.path.dirname(__file__), "previous-session.js"),
            replace_map={
                "CURRENT_INPUT_NAME": name,
                "CurrentPascalInputName": to_pascal_case(name),
            },
        )
        return "\n".join(
            [
                f'<input name="{name}" placeholder="{description}" value="{default}" />',
                f"<script>{script}</script>",
            ]
        )
