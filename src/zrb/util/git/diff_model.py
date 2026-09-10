class DiffResult:
    def __init__(
        self,
        created: list[str] | None = None,
        removed: list[str] | None = None,
        updated: list[str] | None = None,
    ):
        self.created = created if created is not None else []
        self.removed = removed if removed is not None else []
        self.updated = updated if updated is not None else []
