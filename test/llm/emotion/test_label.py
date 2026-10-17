import pytest

from zrb.llm.emotion import get_leading_emotion


@pytest.mark.parametrize(
    "text, emotion",
    [
        ("😊 Done, the tests pass.", "happy"),
        ("  😢 That failed again.", "sad"),
        ("🙂 Here it is.", "neutral"),
        ("Done 😊", None),
        ("", None),
        ("🚀 Shipped.", None),
    ],
)
def test_the_leading_emoji_names_the_emotion(text, emotion):
    assert get_leading_emotion(text) == emotion
