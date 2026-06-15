from unittest import mock

import pytest

from zrb.builtin.json import (
    format_json,
    get_json,
    json_to_yaml,
    minify_json,
    validate_json,
    yaml_to_json,
)
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_format_json():
    res = await format_json.async_run(
        session=get_session(), kwargs={"json": '{"a":1}', "indent": 2}
    )
    assert res == '{\n  "a": 1\n}'


@pytest.mark.asyncio
async def test_minify_json():
    res = await minify_json.async_run(
        session=get_session(), kwargs={"json": '{\n  "a": 1\n}'}
    )
    assert res == '{"a":1}'


@pytest.mark.asyncio
async def test_validate_json():
    s1 = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await validate_json.async_run(session=s1, kwargs={"json": '{"a": 1}'})
    assert s1.final_result is True
    s2 = Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())
    await validate_json.async_run(session=s2, kwargs={"json": "{bad}"})
    assert s2.final_result is False


@pytest.mark.asyncio
async def test_get_json_path():
    res = await get_json.async_run(
        session=get_session(),
        kwargs={
            "json": '{"user": {"roles": ["admin", "dev"]}}',
            "path": "user.roles[0]",
        },
    )
    assert res == "admin"


@pytest.mark.asyncio
async def test_get_json_root_object():
    res = await get_json.async_run(
        session=get_session(), kwargs={"json": '{"a": 1}', "path": ""}
    )
    assert '"a": 1' in res


@pytest.mark.asyncio
async def test_format_json_invalid_raises_clear_error():
    with pytest.raises(ValueError, match="Invalid JSON at line"):
        await format_json.async_run(
            session=get_session(), kwargs={"json": "{bad}", "indent": 2}
        )


@pytest.mark.asyncio
async def test_get_json_missing_path_raises_clear_error():
    with pytest.raises(ValueError, match="not found"):
        await get_json.async_run(
            session=get_session(), kwargs={"json": '{"a": 1}', "path": "a.b.c"}
        )


@pytest.mark.asyncio
async def test_json_to_yaml():
    res = await json_to_yaml.async_run(
        session=get_session(), kwargs={"json": '{"a": 1, "b": [2, 3]}'}
    )
    assert "a: 1" in res
    assert "b:" in res


@pytest.mark.asyncio
async def test_yaml_to_json():
    res = await yaml_to_json.async_run(
        session=get_session(), kwargs={"yaml": "a: 1\nb:\n  - 2\n  - 3\n", "indent": 2}
    )
    assert '"a": 1' in res
    assert '"b": [' in res
