import libcst as cst

from zrb.helper.typecheck import typechecked


@typechecked
class TaskTransformer(cst.CSTTransformer):
    def __init__(self, task_name: str, upstream_task_name: str):
        super().__init__()
        self.task_name: str = task_name
        self.upstream_task_name: str = upstream_task_name
        self._on_task_call = False
        self._upstream_added = False

    def _is_task(self, node: cst.Call) -> bool:
        if not isinstance(node.func, cst.Name) or node.func.value != "Task":
            return False
        # Look for name keyword
        for name_arg in node.args:
            if (
                isinstance(name_arg, cst.Arg)
                and name_arg.keyword.value == "name"
                and name_arg.value.evaluated_value == self.task_name
            ):
                return True
        return False

    def visit_Call(self, node: cst.Call):
        # Visit all function call (or class initiation)
        # If it is the task we seek, flag it
        if self._is_task(node):
            self._on_task_call = True

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        # Remove flags.
        # If upstreams argument not found (see: self.leave_Arg), add it
        if not self._is_task(updated_node):
            return updated_node
        self._on_task_call = False
        if self._upstream_added:
            return updated_node
        new_args = [arg for arg in updated_node.args]
        new_args.append(
            cst.Arg(
                keyword=cst.parse_expression("upstreams"),
                value=cst.List(
                    [cst.Element(cst.parse_expression(self.upstream_task_name))]
                ),
            )
        )
        self._upstream_added = True
        return updated_node.with_changes(args=new_args)

    def leave_Arg(self, orginnal_node: cst.Arg, updated_node: cst.Arg):
        # Once the flag was set (see: self.visit_Call), look for
        # `upstreams` argument and modify the value
        if (
            not self._on_task_call
            or updated_node.keyword is None
            or updated_node.keyword.value != "upstreams"
        ):
            return updated_node
        new_elements = [old_element for old_element in updated_node.value.elements]
        new_elements.append(
            cst.Element(value=cst.parse_expression(self.upstream_task_name))
        )
        self._upstream_added = True
        return updated_node.with_changes(value=cst.List(new_elements))


@typechecked
def add_upstream_to_task(code: str, task_name: str, upstream_task_name: str) -> str:
    """
    Transformer to add an upstream task to a Task object.

    Args:
        code (str): The code to modify.
        task_name (str): Name of the task to modify.
        upstream_task_name (str): Name of the upstream task to add.

    Returns:
        A modified version of the input code with the upstream task added.
    """
    transformer: TaskTransformer = TaskTransformer(task_name, upstream_task_name)
    original_tree: cst.Module = cst.parse_module(code)
    modified_tree: cst.Module = original_tree.visit(transformer)
    return modified_tree.code
