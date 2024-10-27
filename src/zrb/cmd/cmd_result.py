class CmdResult:
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error

    def __repr__(self):
        class_name = self.__class__.__name__
        last_line_output = self.output.split("\n")[-1]
        shown_output = f"...{last_line_output}" if last_line_output != "" else ""
        last_line_error = self.error.split("\n")[-1]
        shown_error = f"...{last_line_error}" if last_line_error != "" else ""
        return f"<{class_name} output={shown_output} error=...{shown_error}>"

    def __str__(self) -> str:
        return self.output
