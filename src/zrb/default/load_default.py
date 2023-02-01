from ..runner import runner
from .show import show_solid_principle


def load_default():
    runner.register(show_solid_principle)
