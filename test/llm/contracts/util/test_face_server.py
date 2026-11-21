"""The face server's contract as zrb speaks it: where the voice is, its token,
and the format both routes carry.

`LLM_VOICE_REMOTE_URL` is the one setting that moves both halves of the voice —
dictation's microphone and speech's speaker — so what it reads as decides both.
These tests are about that reading: the base URL with no trailing slash, the
empty default that keeps the voice on this machine, the `Authorization` header
a server with a token wants, and the body a route may not send.

And the one route whose name zrb does not serve: `/text/in` belongs to the page,
so it is pinned here rather than followed anywhere.
"""

import email.message

import pytest

from zrb.config.config import CFG
from zrb.llm.contracts.util import face_server


def _set(monkeypatch, name, value):
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_{name}", value)


def _format(**overrides):
    headers = email.message.Message()
    for name, value in {
        "X-Sample-Rate": "16000",
        "X-Sample-Width": "2",
        "X-Channels": "1",
        **overrides,
    }.items():
        headers[name] = value
    return headers


def test_no_url_keeps_the_voice_on_this_machine():
    assert face_server.get_remote_url() is None
    assert not face_server.is_remote_voice_selected()


def test_a_url_selects_the_page_for_both_halves(monkeypatch):
    _set(monkeypatch, "LLM_VOICE_REMOTE_URL", "  http://127.0.0.1:7777/  ")

    assert face_server.get_remote_url() == "http://127.0.0.1:7777"
    assert face_server.is_remote_voice_selected()


def test_a_server_without_a_token_wants_no_header(monkeypatch):
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_TOKEN", raising=False)
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_AVATAR_TOKEN", raising=False)

    assert face_server.get_remote_headers() == {}


def test_the_servers_own_token_names_both_sides(monkeypatch):
    """One token, one name: where this setting is unset, the server's own
    `ZRB_AVATAR_TOKEN` is what zrb sends."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_TOKEN", raising=False)
    _set(monkeypatch, "AVATAR_TOKEN", "shared")

    assert face_server.get_remote_headers() == {"Authorization": "Bearer shared"}


def test_this_setting_is_sent_over_the_servers_own(monkeypatch):
    _set(monkeypatch, "LLM_VOICE_REMOTE_TOKEN", "mine")
    _set(monkeypatch, "AVATAR_TOKEN", "theirs")

    assert face_server.get_remote_headers() == {"Authorization": "Bearer mine"}


def test_the_contracts_own_format_is_taken():
    face_server.check_audio_format(_format(), 16000)


@pytest.mark.parametrize(
    "headers",
    [
        _format(**{"X-Sample-Rate": "44100"}),
        _format(**{"X-Sample-Width": "4"}),
        _format(**{"X-Channels": "2"}),
    ],
)
def test_a_body_dictation_cannot_read_is_refused(headers):
    """Nothing here resamples or mixes, so a rate, a width or a channel count
    of the server's choosing is refused rather than heard as noise."""
    with pytest.raises(RuntimeError) as refusal:
        face_server.check_audio_format(headers, 16000)

    assert "dictation reads 16000 Hz" in str(refusal.value)


def test_a_body_naming_no_format_is_refused():
    with pytest.raises(RuntimeError) as refusal:
        face_server.check_audio_format({}, 16000)

    assert "X-Sample-Rate" in str(refusal.value)


def test_the_text_box_route_is_the_pages_name_for_it():
    """`/text/in` is served by the page, so its spelling is a wire name, not an
    internal detail: `zrb-avatar` dispatches on the same string. A rename on
    this side reaches it as a 404, which the reader treats as "no text box
    here" -- the same silence as a zrb with no reader installed, so it would
    fail quietly. Renaming it is therefore a protocol change, and this test is
    where that change has to be stated."""
    assert face_server.TYPED_PATH == "/text/in"
