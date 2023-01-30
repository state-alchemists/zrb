from .action.runner import Runner
from .config.config import env_prefix

runner = Runner(env_prefix=env_prefix)
