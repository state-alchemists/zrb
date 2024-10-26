class CmdResult:
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} output={self.output} error={self.error}>"

    def __str__(self) -> str:
        return self.output
