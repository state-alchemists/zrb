# Disable LLMTask escape detection to prevent terminal interference
import os

from zrb.input.str_input import StrInput
from zrb.task.llm_task import LLMTask

os.environ["ZRB_DISABLE_LLM_ESCAPE_DETECTION"] = "1"
llm_task_core = LLMTask(
    name="llm-anu", input=[StrInput("message")], message="{ctx.input.message}"
)
