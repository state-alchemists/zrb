class SingleSubTreeConfig:
    def __init__(self, repo_url: str, branch: str, prefix: str):
        self.repo_url = repo_url
        self.branch = branch
        self.prefix = prefix


class SubTreeConfig:
    def __init__(self, data: dict[str, SingleSubTreeConfig]):
        self.data = data
