import json


class _JsonModel:
    """A small object that serializes through its own `to_dict`."""

    def to_dict(self) -> dict[str, object]:
        raise NotImplementedError

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class SingleSubTreeConfig(_JsonModel):
    def __init__(self, repo_url: str, branch: str, prefix: str):
        self.repo_url = repo_url
        self.branch = branch
        self.prefix = prefix

    def to_dict(self) -> dict[str, object]:
        return {
            "repo_url": self.repo_url,
            "branch": self.branch,
            "prefix": self.prefix,
        }


class SubTreeConfig(_JsonModel):
    def __init__(self, data: dict[str, SingleSubTreeConfig]):
        self.data = data

    def to_dict(self) -> dict[str, object]:
        return {
            "data": {k: self.data[k].to_dict() for k in self.data},
        }
