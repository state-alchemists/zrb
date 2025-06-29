🔖 [Documentation Home](../../../README.md) > [Task](../../../README.md) > [Core Concepts](../../README.md) > [Task](../README.md) > [Task Types](./README.md) > Scaffolder

# Scaffolder

A task for creating files and directories from templates.

```python
from zrb import Scaffolder, StrInput, cli

# Create a project from a template
create_project = Scaffolder(
    name="create-project",
    description="Create a new project from a template",
    input=StrInput(name="project_name", description="Name of the project"),
    source_path="./templates/basic-project",
    destination_path="./projects/{ctx.input.project_name}",
    transform_content={"PROJECT_NAME": "{ctx.input.project_name}"}
)

cli.add_task(create_project)
```

**When to use**: Use `Scaffolder` when you need to generate files and directories from templates. It's perfect for tasks like creating new projects, generating boilerplate code, or setting up configuration files with customized content.