import os

from zrb.config.config import CFG
from zrb.config.llm_context.config import llm_context_config
from zrb.config.llm_context.workflow import LLMWorkflow


def load_workflow(workflow_name: str | list[str]) -> str:
    """
    Loads and formats one or more workflow documents for LLM consumption.

    Retrieves workflows by name, formats with descriptive headers for LLM context injection.

    Args:
        workflow_name: Name or list of names of the workflow(s) to load

    Returns:
        Formatted workflow content as a string with headers

    Raises:
        ValueError: If any specified workflow name is not found
    """
    names = [workflow_name] if isinstance(workflow_name, str) else workflow_name
    available_workflows = get_available_workflows()
    contents = []
    for name in names:
        workflow = available_workflows.get(name.strip().lower())
        if workflow is None:
            raise ValueError(f"Workflow not found: {name}")
        contents.append(
            "\n".join(
                [
                    f"# {workflow.name}",
                    f"> Workflow Location: `{workflow.path}`",
                    workflow.content,
                ]
            )
        )
    return "\n".join(contents)


def get_available_workflows() -> dict[str, LLMWorkflow]:
    available_workflows = {
        workflow_name.strip().lower(): workflow
        for workflow_name, workflow in llm_context_config.get_workflows().items()
    }
    # Define builtin workflow locations in order of precedence
    builtin_workflow_locations = [
        os.path.expanduser(additional_builtin_workflow_path)
        for additional_builtin_workflow_path in CFG.LLM_BUILTIN_WORKFLOW_PATHS
        if os.path.isdir(os.path.expanduser(additional_builtin_workflow_path))
    ]
    builtin_workflow_locations.append(
        os.path.join(os.path.dirname(__file__), "default_workflow")
    )
    # Load workflows from all locations
    for workflow_location in builtin_workflow_locations:
        if not os.path.isdir(workflow_location):
            continue
        for workflow_name in os.listdir(workflow_location):
            workflow_dir = os.path.join(workflow_location, workflow_name)
            workflow_file = os.path.join(workflow_dir, "workflow.md")
            if not os.path.isfile(workflow_file):
                workflow_file = os.path.join(workflow_dir, "SKILL.md")
                if not os.path.isfile(path=workflow_file):
                    continue
            # Only add if not already defined (earlier locations have precedence)
            if workflow_name not in available_workflows:
                with open(workflow_file, "r") as f:
                    workflow_content = f.read()
                available_workflows[workflow_name] = LLMWorkflow(
                    name=workflow_name,
                    path=workflow_dir,
                    content=workflow_content,
                )
    return available_workflows
