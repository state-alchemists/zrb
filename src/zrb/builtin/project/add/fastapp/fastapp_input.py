import os

from zrb.input.str_input import StrInput

project_dir_input = StrInput(
    name="project-dir",
    description="Project directory",
    prompt="Project directory",
    default=lambda _: os.getcwd(),
)

app_name_input = StrInput(
    name="app",
    description="App name",
    prompt="App name",
)
