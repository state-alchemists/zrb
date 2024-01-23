import datetime
import random

from zrb.helper.python_task import show_lines
from zrb.helper.typing import Any, List
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

_MIN_WIDTH = 10
_MOTIVATIONAL_QUOTES = [
    [
        "The best time to plant a tree was 20 years ago.",
        "The second best time is now.",
        "~ Chinese Proverb",
    ],
    ["The only way to do great work is to love what you do.", "~ Steve Jobs"],
    ["Believe you can and you're halfway there.", "~ Theodore Roosevelt"],
    ["It does not matter how slowly you go as long as you do not stop.", "~ Confucius"],
    ["Everything you've ever wanted is on the other side of fear.", "~ George Addair"],
    [
        "Success is not final, failure is not fatal:",
        "It is the courage to continue that counts.",
        "~ Winston Churchill",
    ],
    [
        "Hardships often prepare ordinary people",
        "for an extraordinary destiny.",
        "~ C.S. Lewis",
    ],
    [
        "Your time is limited, don't waste it living someone else's life.",
        "~ Steve Jobs",
    ],
    ["Don’t watch the clock; do what it does. Keep going.", "~ Sam Levenson"],
    [
        "You are never too old to set another goal or to dream a new dream.",
        "~ C.S. Lewis",
    ],
    [
        "The only limit to our realization of tomorrow",
        "will be our doubts of today.",
        "~ Franklin D. Roosevelt",
    ],
    [
        "Believe in yourself.",
        "You are braver than you think, more talented than you know,"
        "and capable of more than you imagine.",
        "~ Roy T. Bennett",
    ],
    [
        "I can't change the direction of the wind,",
        "but I can adjust my sails to always reach my destination.",
        "~ Jimmy Dean",
    ],
    ["You are enough just as you are.", "~ Meghan Markle"],
    [
        "The future belongs to those",
        "who believe in the beauty of their dreams.",
        "~ Eleanor Roosevelt",
    ],
]


@python_task(
    name="say",
    inputs=[StrInput(name="text", default=""), IntInput(name="width", default=80)],
    description="Say anything, https://www.youtube.com/watch?v=MbPr1oHO4Hw",
    runner=runner,
)
def say(*args: Any, **kwargs: Any):
    width: int = kwargs.get("width", 80)
    if width < _MIN_WIDTH:
        width = _MIN_WIDTH
    text: str = kwargs.get("text", "")
    top_border = "┌" + "─" * (width + 2) + "┐"
    content = ["| " + line + " |" for line in _get_content(text, width)]
    bottom_border = "└" + "─" * (width + 2) + "┘"
    lines = (
        [top_border]
        + content
        + [bottom_border]
        + [
            "      \\",
            "       \\",
            "  o    ___    o",
            "  | ┌-------┐ |",
            "  |(| o   o |)|",
            "    | └---┘ |",
            "    └-------┘",
        ]
    )
    show_lines(kwargs["_task"], *lines)


def _get_content(text: str, width: int) -> List[str]:
    if text == "":
        now = datetime.datetime.now()
        today = "Today is " + now.strftime("%A, %B %d, %Y")
        current_time = "Current time is " + now.strftime("%I:%M %p")
        motivational_quote = random.choice(_MOTIVATIONAL_QUOTES)
        return [
            today.ljust(width),
            current_time.ljust(width),
            "".ljust(width),
        ] + [line.ljust(width) for line in motivational_quote]
    return _split_text_by_width(text, width)


def _split_text_by_width(text: str, width: int) -> List[str]:
    original_lines = text.split("\n")
    new_lines = []
    for original_line in original_lines:
        new_lines += [
            original_line[i : i + width].ljust(width)
            for i in range(0, len(original_line), width)
        ]
    return new_lines
