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
    try:
        subprocess.run(
            ["git", "subtree", "add", "--prefix", prefix, repo_url, branch],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(e.stderr or e.stdout)
    config.data[name] = SingleSubTreeConfig(
        repo_url=repo_url, branch=branch, prefix=prefix
    )
    save_config(config)


def pull_subtree(prefix: str, repo_url: str, branch: str):
    try:
        subprocess.run(
            [
                "git",
                "subtree",
                "pull",
                "--prefix",
                prefix,
                repo_url,
                branch,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(e.stderr or e.stdout)


def push_subtree(prefix: str, repo_url: str, branch: str):
    try:
        subprocess.run(
            [
                "git",
                "subtree",
                "push",
                "--prefix",
                prefix,
                repo_url,
                branch,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(e.stderr or e.stdout)
