"""Fixtures shared by the vosk backend tests: a home directory of its own, so
nothing touches the real ~/.cache, and stand-ins for the two things a model
download talks to — an HTTP response and a `zipfile.ZipFile`."""

import os
import zipfile
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """A home directory of its own, so no test touches the real ~/.cache and
    none depends on it already existing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


@pytest.fixture
def cache_dir(tmp_home):
    """Where a download puts the model, staging directory and all."""
    return os.path.join(os.path.expanduser("~"), ".cache", "vosk")


@pytest.fixture
def fake_response():
    """A stand-in response whose `read` yields *chunks* and then stops."""

    def build(*chunks):
        resp = MagicMock()
        resp.read.side_effect = list(chunks)
        return resp

    return build


@pytest.fixture
def fake_zip():
    """A stand-in `zipfile.ZipFile` listing *members*; *sizes* maps a member
    name to the byte count its header declares."""

    def build(members, sizes=None):
        sizes = sizes or {}
        archive = MagicMock()
        archive.__enter__.return_value = archive
        infos = []
        for name in members:
            info = zipfile.ZipInfo(name)
            info.file_size = sizes.get(name, 0)
            infos.append(info)
        archive.infolist.return_value = infos
        return archive

    return build
