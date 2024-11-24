import os
import subprocess

from pydantic import BaseModel

from zrb.util.git import get_repo_dir


class SingleSubTreeConfig(BaseModel):
    repo_url: str
    branch: str
    prefix: str


class SubTreeConfig(BaseModel):
    data: dict[str, SingleSubTreeConfig]


def load_config() -> SubTreeConfig:
    file_path = os.path.join(get_repo_dir(), "subtrees.json")
    if not os.path.exists(file_path):
        return SubTreeConfig(data={})
    with open(file_path, "r") as f:
        return SubTreeConfig.model_validate_json(f.read())


def save_config(config: SubTreeConfig):
    file_path = os.path.join(get_repo_dir(), "subtrees.json")
    with open(file_path, "w") as f:
        f.write(config.model_dump_json(indent=2))


def add_subtree(name: str, repo_url: str, branch: str, prefix: str):
    config = load_config()
    if os.path.isdir(prefix):
        raise ValueError(f"Directory exists: {prefix}")
    if name in config.data:
        raise ValueError(f"Subtree config already exists: {name}")
    result = subprocess.run(
        ["git", "subtree", "add", "--prefix", prefix, repo_url, branch],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    if result.returncode != 0:
        raise Exception(f"Cannot add subtree, exit code: {result.returncode}")
    config.data[name] = SingleSubTreeConfig(
        repo_url=repo_url, branch=branch, prefix=prefix
    )
    save_config(config)


def pull_all_subtrees():
    config = load_config()
    if not config.data:
        raise ValueError(f"No subtree config found")
    for _, details in config.items():
        subprocess.run(
            [
                "subtree",
                "pull",
                "--prefix",
                details.prefix,
                details.repo_url,
                details.branch,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )


def push_all_subtrees():
    config = load_config()
    if not config.data:
        raise ValueError(f"Subtree config already exists: {name}")
    for _, details in config.items():
        subprocess.run(
            [
                "subtree",
                "push",
                "--prefix",
                details.prefix,
                details.repo_url,
                details.branch,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )