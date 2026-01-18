🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Workflow Configuration

## Overview

The `LLMTask` in `zrb` uses workflows to define the behavior of the LLM agent. Workflows are a set of instructions that guide the agent on how to perform a specific task. For example, the `coding` workflow provides instructions for writing and refactoring code, while the `researching` workflow provides instructions for searching the web and gathering information.

## Configuring Workflows

You can configure the workflows that an `LLMTask` uses with the `workflows` parameter. The `workflows` parameter is a list of strings, where each string is the name of a workflow.

For example, to use the `coding` and `researching` workflows, you would set the `workflows` parameter to `['coding', 'researching']`.

```python
from zrb import LLMTask, runner

llm_task = LLMTask(
    name="my-llm-task",
    workflows=["coding", "researching"],
    message="Research how to implement a feature and then implement it.",
)

if __name__ == "__main__":
    runner.run(llm_task)
```

## Default Workflows

You can set the default workflows for all `LLMTask`s by setting the `ZRB_LLM_DEFAULT_WORKFLOWS` environment variable. The value of this environment variable should be a comma-separated list of workflow names.

For example, to set the default workflows to `coding` and `researching`, you would set the `ZRB_LLM_DEFAULT_WORKFLOWS` environment variable to `coding,researching`.

## Available Workflows

`zrb` comes with a set of built-in workflows that you can use out of the box.

Here are the available built-in workflows:

*   `coding`: For writing and refactoring code.
*   `copywriting`: For writing marketing copy and other content.
*   `researching`: For searching the web and gathering information.

## Custom Workflows

You can also create your own custom workflows. To create a custom workflow, you need to create a directory with a `workflow.md` file in it. The `workflow.md` file should contain the instructions for the workflow.

You can then add the path to your custom workflow directory to the `ZRB_LLM_BUILTIN_WORKFLOW_PATHS` environment variable. `zrb` will then be able to find and use your custom workflow.

`ZRB_LLM_BUILTIN_WORKFLOW_PATHS` is a colon-separated list of paths to custom workflow directories.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)
