from zrb.builtin.group import explain_group
from zrb.helper.python_task import show_lines
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="solid-principle",
    group=explain_group,
    description="Explain SOLID principle",
    runner=runner,
)
async def explain_solid_principle(*args: Any, **kwargs: Any):
    show_lines(
        kwargs["_task"],
        "S - Single Responsibility Principle",
        "O - Open/Closed Principle",
        "L - Liskov’s Substitution Principle",
        "I - Interface Segregation Principle",
        "D - Dependency Inversion Principle",
        "",
        "In software development, Object-Oriented Design plays a crucial role when it comes to writing flexible, scalable, maintainable, and reusable code. There are so many benefits of using OOD but every developer should also have the knowledge of the SOLID principle for good object-oriented design in programming. The SOLID principle was introduced by Robert C. Martin, also known as Uncle Bob and it is a coding standard in programming.",  # noqa
        "",
        "The SOLID principle helps in reducing tight coupling. Tight coupling means a group of classes are highly dependent on one another which you should avoid in your code. Opposite of tight coupling is loose coupling and your code is considered as a good code when it has loosely-coupled classes. Loosely coupled classes minimize changes in your code, helps in making code more reusable, maintainable, flexible and stable.",  # noqa
    )


@python_task(
    name="yagni-principle",
    group=explain_group,
    description="Explain YAGNI principle",
    runner=runner,
)
async def explain_yagni_principle(*args: Any, **kwargs: Any):
    show_lines(
        kwargs["_task"],
        "Y - You",
        "A - Aren't",
        "G - Gonna",
        "N - Need",
        "I - It",
        "",
        'YAGNI principle ("You Aren\'t Gonna Need It") is a practice in software development which states that features should only be added when required.',  # noqa
        "",
        "As a part of the extreme programming (XP) philosophy, YAGNI trims away excess and inefficiency in development to facilitate the desired increased frequency of releases.",  # noqa
    )


@python_task(
    name="dry-principle",
    group=explain_group,
    description="Explain DRY principle",
    runner=runner,
)
async def explain_dry_principle(*args: Any, **kwargs: Any):
    show_lines(
        kwargs["_task"],
        "D - Don't",
        "R - Repeat",
        "Y - Yourself",
        "",
        '"Don\'t repeat yourself" (DRY) is a principle of software development aimed at reducing repetition of information which is likely to change, replacing it with abstractions that are less likely to change, or using data normalization which avoids redundancy in the first place.',  # noqa
        "",
        'The DRY principle is stated as "Every piece of knowledge must have a single, unambiguous, authoritative representation within a system". The principle has been formulated by Andy Hunt and Dave Thomas in their book The Pragmatic Programmer.',  # noqa
    )


@python_task(
    name="kiss-principle",
    group=explain_group,
    description="Explain KISS principle",
    runner=runner,
)
async def explain_kiss_principle(*args: Any, **kwargs: Any):
    show_lines(
        kwargs["_task"],
        "K - Keep",
        "I - It",
        "S - Simple",
        "S - Stupid",
        "",
        'KISS, an acronym for "Keep it simple, stupid!", is a design principle noted by the U.S. Navy in 1960. First seen partly in American English by at least 1938, the KISS principle states that most systems work best if they are kept simple rather than made complicated; therefore, simplicity should be a key goal in design, and unnecessary complexity should be avoided.',  # noqa
    )


@python_task(
    name="zen-of-python",
    group=explain_group,
    description="Explain Zen of Python",
    runner=runner,
)
async def explain_zen_of_python(*args: Any, **kwargs: Any):
    show_lines(
        kwargs["_task"],
        "Beautiful is better than ugly.",
        "Explicit is better than implicit.",
        "Simple is better than complex.",
        "Complex is better than complicated.",
        "Flat is better than nested.",
        "Sparse is better than dense.",
        "Readability counts.",
        "Special cases aren't special enough to break the rules.",
        "Although practicality beats purity.",
        "Errors should never pass silently.",
        "Unless explicitly silenced.",
        "In the face of ambiguity, refuse the temptation to guess.",
        "There should be one-- and preferably only one --obvious way to do it.",  # noqa
        "Although that way may not be obvious at first unless you're Dutch.",
        "Now is better than never.",
        "Although never is often better than *right* now.",
        "If the implementation is hard to explain, it's a bad idea.",
        "If the implementation is easy to explain, it may be a good idea.",
        "Namespaces are one honking great idea -- let's do more of those!",
    )
