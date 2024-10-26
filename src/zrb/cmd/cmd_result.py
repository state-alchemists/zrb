class CmdResult:
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error

    def __str__(self) -> str:
        return self.output
