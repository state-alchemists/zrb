import os

from zrb.config.config import CFG
from zrb.config.llm_context.config import llm_context_config
from zrb.config.llm_context.workflow import LLMWorkflow
from zrb.context.any_context import AnyContext
from zrb.xcom.xcom import Xcom

LLM_LOADED_WORKFLOW_XCOM_NAME = "_llm_loaded_workflow_name"


def load_workflow(ctx: AnyContext, workflow_name: str | list[str]) -> str:
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
    llm_loaded_workflow_xcom = get_llm_loaded_workflow_xcom(ctx)
    llm_loaded_workflow_xcom.push(names)
    return "\n".join(contents)


def get_llm_loaded_workflow_xcom(ctx: AnyContext) -> Xcom:
    if LLM_LOADED_WORKFLOW_XCOM_NAME not in ctx.xcom:
        ctx.xcom[LLM_LOADED_WORKFLOW_XCOM_NAME] = Xcom([])
    return ctx.xcom[LLM_LOADED_WORKFLOW_XCOM_NAME]


def get_available_workflows() -> dict[str, LLMWorkflow]:
    available_workflows = {
        workflow_name.strip().lower(): workflow
        for workflow_name, workflow in llm_context_config.get_workflows().items()
    }
    workflow_hidden_folder = f".{CFG.ROOT_GROUP_NAME}"
    # Define workflow locations in order of precedence
    default_workflow_locations = (
        [
            # Project specific + user specific workflows
            os.path.join(
                os.path.dirname(__file__), workflow_hidden_folder, "workflows"
            ),
            os.path.join(os.path.dirname(__file__), workflow_hidden_folder, "skills"),
            os.path.join(os.path.dirname(__file__), ".claude", "skills"),
            os.path.join(os.path.expanduser("~"), workflow_hidden_folder, "workflows"),
            os.path.join(os.path.expanduser("~"), workflow_hidden_folder, "skills"),
            os.path.join(os.path.expanduser("~"), ".claude", "skills"),
        ]
        + [
            # User defined builtin workflows
            os.path.expanduser(additional_builtin_workflow_path)
            for additional_builtin_workflow_path in CFG.LLM_BUILTIN_WORKFLOW_PATHS
            if os.path.isdir(os.path.expanduser(additional_builtin_workflow_path))
        ]
        + [
            # Zrb builtin workflows
            os.path.join(os.path.dirname(__file__), "default_workflow"),
        ]
    )
    # Load workflows from all locations
    for workflow_location in default_workflow_locations:
        if not os.path.isdir(workflow_location):
            continue
        for workflow_name in os.listdir(workflow_location):
            workflow_dir = os.path.join(workflow_location, workflow_name)
            workflow_file = _get_workflow_file_name(workflow_dir)
            if not workflow_file:
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


def _get_workflow_file_name(workflow_dir: str) -> str | None:
    workflow_file = os.path.join(workflow_dir, "workflow.md")
    if os.path.isfile(workflow_file):
        return workflow_file
    workflow_file = os.path.join(workflow_dir, "WORKFLOW.md")
    if os.path.isfile(workflow_file):
        return workflow_file
    workflow_file = os.path.join(workflow_dir, "SKILL.md")
    if os.path.isfile(workflow_file):
        return workflow_file
    return None
