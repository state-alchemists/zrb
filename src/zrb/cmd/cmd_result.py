class CmdResult:
    def __init__(self, output: str, error: str, display: str):
        """Hold the captured output of a finished command.

        Args:
            output: Everything the command wrote to stdout.
            error: Everything the command wrote to stderr.
            display: The output as shown to the user, which may be truncated or
                styled where `output` is raw.
        """
        self.output = output
        self.error = error
        self.display = display

    def __repr__(self):
        class_name = self.__class__.__name__
        last_line_output = self.output.split("\n")[-1]
        shown_output = f"...{last_line_output}" if last_line_output != "" else ""
        last_line_error = self.error.split("\n")[-1]
        shown_error = f"...{last_line_error}" if last_line_error != "" else ""
        return f"<{class_name} output={shown_output} error=...{shown_error}>"

    def __str__(self) -> str:
        return self.output
