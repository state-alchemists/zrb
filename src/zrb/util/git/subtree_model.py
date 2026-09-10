import json
from typing import Any


class SingleSubTreeConfig:
    def __init__(self, repo_url: str, branch: str, prefix: str):
        self.repo_url = repo_url
        self.branch = branch
        self.prefix = prefix

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "branch": self.branch,
            "prefix": self.prefix,
        }

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class SubTreeConfig:
    def __init__(self, data: dict[str, SingleSubTreeConfig]):
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": {k: self.data[k].to_dict() for k in self.data},
        }

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
