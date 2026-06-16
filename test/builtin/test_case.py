from unittest import mock

import pytest

from zrb.builtin.case import convert_case, slugify
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.mark.parametrize(
    "style, expected",
    [
        ("snake", "hello_world_foo"),
        ("kebab", "hello-world-foo"),
        ("constant", "HELLO_WORLD_FOO"),
        ("camel", "helloWorldFoo"),
        ("pascal", "HelloWorldFoo"),
        ("title", "Hello World Foo"),
    ],
)
@pytest.mark.asyncio
async def test_convert_case(style, expected):
    res = await convert_case.async_run(
        session=get_session(), kwargs={"text": "hello world foo", "style": style}
    )
    assert res == expected


@pytest.mark.asyncio
async def test_convert_case_from_camel():
    res = await convert_case.async_run(
        session=get_session(), kwargs={"text": "helloWorldFoo", "style": "snake"}
    )
    assert res == "hello_world_foo"


@pytest.mark.asyncio
async def test_slugify():
    res = await slugify.async_run(
        session=get_session(), kwargs={"text": "Héllo, World!"}
    )
    assert res == "hello-world"
