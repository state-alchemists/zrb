from pydantic import BaseModel


class SingleSubTreeConfig(BaseModel):
    repo_url: str
    branch: str
    prefix: str


class SubTreeConfig(BaseModel):
    data: dict[str, SingleSubTreeConfig]
