import asyncio
from typing import Any, TextIO


class StdUI:
    """Standard UI implementation of UIProtocol for terminal environments."""

    async def ask_user(self, prompt: str) -> str:
        """Prompt user via CLI input."""
        import sys

        from prompt_toolkit import PromptSession
        from prompt_toolkit.output import create_output

        # Always output to stderr to avoid polluting stdout
        output = create_output(stdout=sys.stderr)
        session = PromptSession(output=output)

        try:
            user_input = await session.prompt_async(prompt)
            return user_input.strip()
        except KeyboardInterrupt:
            # Let it propagate so the task runner can catch it or exit gracefully
            raise
        except EOFError:
            return ""

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Print output to stderr."""
        import sys

        from zrb.util.cli.style import stylize_faint

        content = sep.join(str(v) for v in values) + end
        if kind != "text":
            content = stylize_faint(content)
        sys.stderr.write(content)
        if flush:
            sys.stderr.flush()

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Stream output immediately (same as append_to_output for StdUI).

        For StdUI, there's no buffering, so this is identical to append_to_output.
        """
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run interactive commands using subprocess."""
        import subprocess

        def _run():
            return subprocess.run(cmd, shell=shell)

        return await asyncio.to_thread(_run)
