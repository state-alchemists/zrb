from ...action.runner import Runner
from .solid_principle import show_solid_principle


def register_show(runner: Runner):
    runner.register(show_solid_principle)
