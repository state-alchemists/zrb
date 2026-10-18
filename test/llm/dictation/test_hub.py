"""Hugging Face models come from the local cache before the Hub."""

from zrb.llm.dictation.hub import get_hub_path


class FakeHub:
    """A `snapshot_download` stand-in, with *cached* repos already on disk."""

    def __init__(self, *cached: str):
        self.cached = set(cached)
        self.asked: list[tuple[tuple[str, ...], bool]] = []

    def download(self, *args: str, local_files_only: bool = False) -> str:
        self.asked.append((args, local_files_only))
        if local_files_only and args[0] not in self.cached:
            # What huggingface_hub raises: `LocalEntryNotFoundError`, an OSError.
            raise FileNotFoundError(args[0])
        self.cached.add(args[0])
        return f"/cache/{'/'.join(args)}"


def test_a_cached_model_is_used_without_asking_the_hub():
    hub = FakeHub("me/model")

    assert get_hub_path(hub.download, "me/model") == "/cache/me/model"
    assert hub.asked == [(("me/model",), True)]


def test_a_model_not_cached_yet_is_downloaded():
    hub = FakeHub()

    assert get_hub_path(hub.download, "me/model", "a.onnx") == "/cache/me/model/a.onnx"
    assert hub.asked == [
        (("me/model", "a.onnx"), True),
        (("me/model", "a.onnx"), False),
    ]
