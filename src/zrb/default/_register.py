from ..action.runner import Runner
from .show._register import register_show


def register_default(runner: Runner):
    register_show(runner)
