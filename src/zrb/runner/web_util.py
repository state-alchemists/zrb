from pydantic import BaseModel


class NewSessionResponse(BaseModel):
    session_name: str


def url_to_args(url: str) -> list[str]:
    stripped_url = url.strip("/")
    return [part for part in stripped_url.split("/") if part.strip() != ""]


def node_path_to_url(args: list[str]) -> str:
    pruned_args = [part for part in args if part.strip() != ""]
    stripped_url = "/".join(pruned_args)
    return f"/{stripped_url}/"
