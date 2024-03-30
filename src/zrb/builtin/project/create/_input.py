import os

from zrb.task_input.str_input import StrInput

SYSTEM_USER = os.getenv("USER", "incognito")

project_name_input = StrInput(
    name="project-name",
    shortcut="n",
    description="Project name",
    prompt="Project name (can be empty)",
    default="",
)

project_author_name_input = StrInput(
    name="project-author-name",
    prompt="Project author name",
    description="Project author name",
    default=SYSTEM_USER,
)

project_author_email_input = StrInput(
    name="project-author-email",
    prompt="Project author email",
    description="Project author email",
    default=f"{SYSTEM_USER}@gmail.com",
)

project_description_input = StrInput(
    name="project-description",
    description="Project description",
    prompt="Project description",
    default="Just another Zrb project",
)
