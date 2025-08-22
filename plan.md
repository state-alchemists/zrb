My goal is to add a `to_fn` method to the `BaseTask` class in `src/zrb/task/base_task.py`. This method will convert a task into a callable Python function with a proper signature and docstring, making it more user-friendly and introspectable.

Here is my step-by-step plan:

1.  **Define `to_fn` Method**: I will add a new method, `to_fn`, to the `BaseTask` class in `/root/zrb/src/zrb/task/base_task.py`.

2.  **Create a Wrapper Function**: Inside `to_fn`, I will define and return a nested wrapper function. This function will:
    a.  Accept keyword arguments (`**kwargs`) that correspond to the task's inputs.
    b.  Instantiate `SharedContext` and `Session`, which are required to execute the task.
    c.  Convert the input `kwargs` to the `str_kwargs` format expected by the task's `run` method.
    d.  Call the `self.run` method with the created session and converted arguments, then return the result.

3.  **Generate Dynamic Docstring**: I will create a comprehensive docstring for the wrapper function by:
    a.  Using the task's `description` as the main summary.
    b.  Appending an "Args:" section that details each of the task's inputs, including their descriptions and default values.

4.  **Generate Dynamic Signature**: I will use Python's `inspect` module to build a function signature that matches the task's inputs. This will involve:
    a.  Iterating over `self.inputs`.
    b.  Creating an `inspect.Parameter` for each input, preserving its name and default value.
    c.  Assembling these parameters into an `inspect.Signature` object.
    d.  Assigning the signature to the wrapper function's `__signature__` attribute, making it visible to tools like `help()` and enabling features like tab-completion.

5.  **Set Function Name**: I will set the `__name__` attribute of the wrapper function to the task's name for better representation.

By following these steps, I will successfully create a `to_fn` method that transforms any `BaseTask` into a standard, well-documented Python function.

```python
def to_fn(self):
    from inspect import Parameter, Signature

    from zrb.context.shared_context import SharedContext
    from zrb.session.session import Session

    def task_runner_fn(**kwargs):
        str_kwargs = {k: str(v) for k, v in kwargs.items()}
        shared_ctx = SharedContext()
        session = Session(shared_ctx=shared_ctx)
        return self.run(session=session, str_kwargs=str_kwargs)

    # Create docstring
    doc = f"{self.description}\n\n"
    if len(self.inputs) > 0:
        doc += "Args:\n"
        for inp in self.inputs:
            doc += f"    {inp.name}: {inp.description}"
            if inp.default is not None:
                doc += f" (default: {inp.default})"
            doc += "\n"
    task_runner_fn.__doc__ = doc

    # Create signature
    params = []
    for inp in self.inputs:
        params.append(
            Parameter(
                name=inp.name,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=inp.default
                if inp.default is not None
                else Parameter.empty,
            )
        )
    sig = Signature(params)
    task_runner_fn.__signature__ = sig
    task_runner_fn.__name__ = self.name

    return task_runner_fn
```