🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Extending Task

There are some methods you need to know whenever you decide to extend a Task.

- `run(self, *args: Any, **kwargs: Any) -> Any`: Actions to do when the task is started.
- `check(self) -> bool`: Actions to confirm whether a Task is ready.
- `inject_env_files(self)`: Actions to add environment files.
- `inject_envs(self)`: Actions to add environments.
- `inject_inputs(self)`: Actions to add inputs.
- `inject_checkers(self)`: Actions to add checkers.
- `inject_upstreams(self)`: Actions to add upstreams.
- `print_result(self, result: Any)`: Define how to print Task's run result.

You can also use the following methods:

- XCom related
    - `set_xcom(self, key: str, value: Any) -> str`
    - `set_task_xcom(self, key: str, value: Any) -> str`
    - `get_xcom(self, key: str) -> str`
- Render value
    - `render_any(self, value: Any, data: Optional[Mapping[str, Any]]) -> Any`
    - `render_float(self, value: Union[JinjaTemplate, float], data: Optional[Mapping[str, Any]]) -> float`
    - `render_int(self, value: Union[JinjaTemplate, int], data: Optional[Mapping[str, Any]]) -> int`
    - `render_bool(self, value: Union[JinjaTemplate, bool], data: Optional[Mapping[str, Any]]) -> bool`
    - `render_str(self, value: Union[JinjaTemplate, str], data: Optional[Mapping[str, Any]]) -> str`
    - `render_file(self, path: JinjaTemplate, data: Optional[Mapping[str, Any]]) -> str`

Let's see an example

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
