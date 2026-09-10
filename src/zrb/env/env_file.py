from dotenv import dotenv_values

from zrb.attr.type import StrAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.env_map import EnvMap
from zrb.util.attr import get_str_attr


class EnvFile(EnvMap):
    def __init__(
        self,
        path: StrAttr,
        link_to_os: bool = True,
        os_prefix: str | None = None,
    ):
        """Load environment variables for a task from a dotenv file.

        Args:
            path: Path to the `.env` file. A literal, a `Tpl` rendered against
                the context, or a callable taking it.
            link_to_os: Whether an OS variable of the same name overrides the
                file's value.
            os_prefix: Prefix for the OS lookup, so `DEV` reads `DEV_DB_HOST` for
                a file entry named `DB_HOST`.
        """
        super().__init__(vars={}, link_to_os=link_to_os, os_prefix=os_prefix)
        self._file_path = path

    def _get_env_map(self, shared_ctx: AnySharedContext) -> dict[str, str]:
        file_path = get_str_attr(shared_ctx, self._file_path, ".env")
        return {
            key: value
            for key, value in dotenv_values(file_path).items()
            if value is not None
        }
