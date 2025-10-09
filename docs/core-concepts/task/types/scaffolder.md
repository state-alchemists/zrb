🔖 [Documentation Home](../../../../README.md) > [Core Concepts](../../../README.md) > [Task](../../README.md) > [Task Types](./README.md) > Scaffolder

# `Scaffolder`

The `Scaffolder` task is a powerful tool for generating files and directories from templates. It allows you to create new projects, generate boilerplate code, or set up configuration files with customized content based on user inputs.

## Example

Let's say you have a template for a basic Python project. You can use `Scaffolder` to create a new project from this template, customizing the project name.

```python
from zrb import Scaffolder, StrInput, cli

# A task to create a new project from a template directory
create_project = Scaffolder(
    name="create-project",
    description="Create a new project from a template",
    input=StrInput(name="project_name", description="Name of the new project"),
    
    # The directory containing your template files
    source_path="./templates/basic-project",
    
    # The destination path, which can be dynamic based on input
    destination_path="./projects/{ctx.input.project_name}",
    
    # A dictionary of content to find and replace within the template files
    transform_content={"PROJECT_NAME_PLACEHOLDER": "{ctx.input.project_name}"}
)

cli.add_task(create_project)
```

In this example, the `Scaffolder` will:
1.  Ask the user for a `project_name`.
2.  Copy the contents of `./templates/basic-project` to a new directory, e.g., `./projects/my-new-app`.
3.  In all the copied files, it will replace any occurrence of the string `PROJECT_NAME_PLACEHOLDER` with the name provided by the user.

**When to use**: Use `Scaffolder` whenever you need to automate the creation of structured files and directories. It's perfect for "new project" wizards, generating modules or components, and ensuring consistency in your codebase.