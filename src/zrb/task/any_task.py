from zrb.helper.typing import (
    Any, Callable, Iterable, JinjaTemplate, List, Mapping, Optional, Union,
    TypeVar
)
from abc import ABC, abstractmethod
from zrb.task_env.env_file import EnvFile
from zrb.task_env.env import Env
from zrb.task_input.any_input import AnyInput

# flake8: noqa E501
TAnyTask = TypeVar('TAnyTask', bound='AnyTask')


class AnyTask(ABC):
    '''
    Abstract base class for defining tasks in a task management system.

    This class acts as a template for creating new task types. To define a new task, 
    extend this class and implement all its abstract methods. The `AnyTask` class is 
    considered atomic and is not broken into multiple interfaces.

    Subclasses should implement the abstract methods to define custom behavior for 
    task execution, state transitions, and other functionalities.
    '''

    @abstractmethod
    def copy(self) -> TAnyTask:
        '''
        Creates and returns a copy of the current task.

        The copied task can be modified using various setter methods like `set_name`, 
        `set_description`, and others, depending on the subclass implementation.

        Returns:
            TAnyTask: A copy of the current task.

        Example:
            >>> from zrb import Task
            >>> task = Task(name='my-task', cmd='echo hello')
            >>> copied_task = task.copy()
            >>> copied_task.set_name('new_name')
        '''
        pass

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        '''
        Executes the main logic of the task.

        This asynchronous method should be implemented in subclasses to define the 
        task's primary functionality. The specific behavior and the return value 
        depend on the task's nature and purpose.

        Args:
            args (Any): Variable length argument list.
            kwargs (Any): Arbitrary keyword arguments.

        Returns:
            Any: The result of the task execution, the type of which is determined by 
            the specific task implementation.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def run(self, *args: Any, **kwargs: Any) -> int:
            >>>         self.print_out('Doing some calculation')
            >>>         return 42
        '''
        pass

    @abstractmethod
    async def check(self) -> bool:
        '''
        Checks if the current task is `ready`.

        Any other tasks depends on the current task, will be `started` once the current task is `ready`.

        This method should be implemented to define the criteria for considering the task 
        `ready`. The specifics of this completion depend on the task's 
        nature and the subclass implementation.

        Returns:
            bool: True if the task is completed, False otherwise.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def run(self, *args: Any, **kwargs: Any) -> int:
            >>>         self.print_out('Doing some calculation')
            >>>         self._completed = True
            >>>         return 42
            >>>     async def check(self) -> bool:
            >>>         return self._completed
        '''
        pass

    @abstractmethod
    async def on_triggered(self):
        '''
        Defines actions to perform when the task status is set to `triggered`.

        Implement this method to specify behavior when the task transitions to the 
        `triggered` state. This could involve setting up prerequisites or sending 
        notifications.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_triggered(self):
            >>>         self.log_info('Task has been triggered')
        '''
        pass

    @abstractmethod
    async def on_waiting(self):
        '''
        Defines actions to perform when the task status is set to `waiting`.

        Implement this method to specify behavior when the task transitions to the 
        `waiting` state. This state usually indicates the task is waiting for some 
        condition or prerequisite to be met.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_waiting(self):
            >>>         self.log_info('Task is waiting to be started')
        '''
        pass

    @abstractmethod
    async def on_skipped(self):
        '''
        Defines actions to perform when the task status is set to `skipped`.

        Implement this method to specify behavior when the task is skipped. This could 
        include logging information, cleaning up resources, or any other necessary steps.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_skipped(self):
            >>>         self.log_info('Task was skipped') 
        '''
        pass

    @abstractmethod
    async def on_started(self):
        '''
        Defines actions to perform when the task status is set to 'started'.

        Implement this method to specify behavior when the task starts its execution. This 
        could involve initializing resources, logging, or other startup procedures.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_started(self):
            >>>         self.log_info('Task has started')
        '''
        pass

    @abstractmethod
    async def on_ready(self):
        '''
        Defines actions to be performed when the task status is `ready`.

        This asynchronous method should be implemented in subclasses to specify 
        actions that occur when the task reaches the `ready` state. This can include 
        any cleanup, notification, or follow-up actions specific to the task.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_ready(self):
            >>>         self.print_out('The task is ready')
        '''
        pass

    @abstractmethod
    async def on_failed(self, is_last_attempt: bool, exception: Exception):
        '''
        Specifies the behavior when the task execution fails.

        This asynchronous method should be implemented in subclasses to handle task 
        failure scenarios. It can include logging the error, performing retries, or 
        any other failure handling mechanisms.

        Args:
            is_last_attempt (bool): Indicates if this is the final retry attempt.
            exception (Exception): The exception that caused the task to fail.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_failed(self, is_last_attempt: bool, exception: Exception):
            >>>         if is_last_attempt:
            >>>             self.print_out('The task has failed with no remaining retries')
            >>>         else:
            >>>             self.print_out('The task failed, retrying...')
        '''
        pass

    @abstractmethod
    async def on_retry(self):
        '''
        Defines actions to perform when the task is retried.

        Implement this method to specify behavior when the task is retried after a failure. 
        This could include resetting states, logging the retry attempt, or other necessary 
        steps before re-execution.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def on_retry(self):
            >>>         self.log_info('Retrying task')
        '''
        pass

    @abstractmethod
    def to_function(
        self,
        env_prefix: str = '',
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True
    ) -> Callable[..., Any]:
        '''
        Converts the current task into a callable function.

        This method should be implemented to allow the task to be executed as a function. 
        Parameters can be used to modify the behavior of the generated function, such as 
        raising errors, asynchronous execution, and logging.

        Args:
            env_prefix (str): A prefix for environment variables.
            raise_error (bool): Whether to raise an error if the task execution fails.
            is_async (bool): Whether the resulting function should be asynchronous.
            show_done_info (bool): Whether to show information upon task completion.

        Returns:
            Callable[..., Any]: A callable representation of the task.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     async def run(self, *args: Any, **kwargs: Any) -> int:
            >>>         self.print_out('Doing some calculation')
            >>>         return 42
            >>>
            >>> task = MyTask()
            >>> fn = task.to_function()
            >>> fn()
        '''
        pass

    @abstractmethod
    def insert_upstream(self, *upstreams: TAnyTask):
        '''
        Inserts one or more `AnyTask` instances at the beginning of the current task's upstream list.

        This method is used to define dependencies for the current task. Tasks in the upstream list are 
        executed before the current task. Adding a task to the beginning of the list means it will be 
        executed earlier than those already in the list.

        Args:
            upstreams (TAnyTask): One or more task instances to be added to the upstream list.

        Example:
            >>> from zrb import Task
            >>> task = Task(name='task')
            >>> upstream_task = Task(name='upstream-task')
            >>> task.insert_upstream(upstream_task)
        '''
        pass

    @abstractmethod
    def add_upstream(self, *upstreams: TAnyTask):
        '''
        Adds one or more `AnyTask` instances to the end of the current task's upstream list.

        This method appends tasks to the upstream list, indicating that these tasks should be executed 
        before the current task, but after any tasks already in the upstream list.

        Args:
            upstreams (TAnyTask): One or more task instances to be added to the upstream list.

        Example:
            >>> from zrb import Task
            >>> task = Task(name='task')
            >>> upstream_task = Task(name='upstream-task')
            >>> task.add_upstream(upstream_task)
        '''
        pass

    @abstractmethod
    def insert_input(self, *inputs: AnyInput):
        '''
        Inserts one or more `AnyInput` instances at the beginning of the current task's input list.

        This method is used to add inputs that the task will process. Inserting an input at the beginning 
        of the list gives it precedence over those already present.

        Args:
            inputs (AnyInput): One or more input instances to be added to the input list.

        Example:
            >>> from zrb import Task, Input
            >>> task = Task(name='task')
            >>> email_input = Input(name='email-address')
            >>> task.insert_input(email_input)
        '''
        pass

    @abstractmethod
    def add_input(self, *inputs: AnyInput):
        '''
        Adds one or more `AnyInput` instances to the end of the current task's input list.

        This method is used to append inputs for the task to process, placing them after any inputs 
        already specified.

        Args:
            inputs (AnyInput): One or more input instances to be added to the input list.

        Example:
            >>> from zrb import Task, Input
            >>> task = Task(name='task')
            >>> email_input = Input(name='email-address')
            >>> task.add_input(email_input)
        '''
        pass

    @abstractmethod
    def insert_env(self, *envs: Env):
        '''
        Inserts one or more `Env` instances at the beginning of the current task's environment variable list.

        This method allows for setting or overriding environment variables for the task, with earlier entries 
        having precedence over later ones.

        Args:
            envs (Env): One or more environment variable instances to be added.

        Example:
            >>> from zrb import Task, Env
            >>> task = Task(name='task')
            >>> db_url_env = Env(name='DATABASE_URL', value='postgresql://...')
            >>> task.insert_env(env_var)
        '''
        pass

    @abstractmethod
    def add_env(self, *envs: Env):
        '''
        Adds one or more `Env` instances to the end of the current task's environment variable list.

        Use this method to append environment variables for the task, which will be used after 
        any variables already set.

        Args:
            envs (Env): One or more environment variable instances to be added.
        
        Example:
            >>> from zrb import Task, Env
            >>> task = Task(name='task')
            >>> db_url_env = Env(name='DATABASE_URL', value='postgresql://...')
            >>> task.add_env(env_var)
        '''
        pass

    @abstractmethod
    def insert_env_file(self, *env_files: EnvFile):
        '''
        Inserts one or more `EnvFile` instances at the beginning of the current task's environment file list.

        This method is used to specify environment variable files whose contents should be loaded 
        before those of any files already in the list. This is useful for overriding or setting 
        additional environment configurations.

        Args:
            env_files (EnvFile): One or more environment file instances to be added.

        Example:
            >>> from zrb import Task, EnvFile
            >>> task = Task()
            >>> env_file = EnvFile(path='config.env')
            >>> task.insert_env_file(env_file)
        '''
        pass

    @abstractmethod
    def add_env_file(self, *env_files: EnvFile):
        '''
        Adds one or more `EnvFile` instances to the end of the current task's environment file list.

        Use this method to append environment file references, which will be processed after 
        any files already specified. This allows for supplementing the existing environment 
        configuration.

        Args:
            env_files (EnvFile): One or more environment file instances to be added.

        Example:
            >>> from zrb import Task, EnvFile
            >>> task = Task()
            >>> env_file = EnvFile(path='config.env')
            >>> task.add_env_file(env_file)
        '''
        pass

    @abstractmethod
    def _set_execution_id(self, execution_id: str):
        '''
        Sets the execution ID for the current task.

        This method is intended for internal use to assign a unique identifier to the task's execution. 
        This ID can be used for tracking, logging, and inter-task communication.

        This method should not be used externally, as it is meant to be managed within the task system.

        Args:
            execution_id (str): A string representing the unique execution ID.
        '''
        pass

    @abstractmethod
    def set_name(self, new_name: str):
        '''
        Sets a new name for the current task.

        This method is used to update the task's name, typically after creating a copy of an existing task. 
        The new name helps in differentiating the task in the task management system.

        Args:
            new_name (str): A string representing the new name to be assigned to the task.
        '''
        pass

    @abstractmethod
    def set_description(self, new_description: str):
        '''
        Sets a new description for the current task.

        This method allows updating the task's description to provide more context or details about its purpose and behavior. 
        Useful for enhancing clarity and maintainability in the task management system.

        Args:
            new_description (str): A string representing the new description of the task.
        '''
        pass

    @abstractmethod
    def set_icon(self, new_icon: str):
        '''
        Assigns a new icon to the current task.

        This method is used for setting or updating the task's icon, which can be utilized for visual representation 
        in a user interface. The icon should ideally be a string identifier that maps to an actual graphical resource.

        Args:
            new_icon (str): A string representing the icon identifier for the task.
        '''
        pass

    @abstractmethod
    def set_color(self, new_color: str):
        '''
        Defines a new color for the current task.

        This method updates the color associated with the task. This can be useful for categorization, 
        priority indication, or visual differentiation in a UI.

        Args:
            new_color (str): A string representing the color to be assigned to the task. 
        '''
        pass

    @abstractmethod
    def set_should_execute(
        self, should_execute: Union[bool, str, Callable[..., bool]]
    ):
        '''
        Determines whether the task should execute.

        This method configures the execution criteria for the task. It can be set as a boolean value, 
        a string representing a condition, or a callable that returns a boolean. This is useful for 
        conditional task execution based on dynamic criteria.

        Args:
            should_execute (Union[bool, str, Callable[..., bool]]): The condition to determine if the task should execute. 
        '''
        pass

    @abstractmethod
    def set_retry(self, new_retry: int):
        '''
        Sets the number of retry attempts for the task.

        This method configures how many times the task should be retried in case of failure. 
        It's essential for tasks that may fail transiently and need multiple attempts for successful execution.

        Args:
            new_retry (int): An integer representing the number of retry attempts.
        '''
        pass

    @abstractmethod
    def set_retry_interval(self, new_retry_interval: Union[float, int]):
        '''
        Specifies the interval between retry attempts for the task.

        This method sets the duration to wait before retrying the task after a failure. 
        This can help in scenarios where immediate retry is not desirable or effective.

        Args:
            new_retry_interval (Union[float, int]): The time interval (in seconds) to wait before a retry attempt. 
        '''
        pass

    @abstractmethod
    def set_checking_interval(self, new_checking_interval: Union[float, int]):
        '''
        Sets the interval for checking the task's readiness or completion status.

        This method defines how frequently the system should check if the task is ready or completed. 
        It's useful for tasks that have an indeterminate completion time.

        Args:
            new_checking_interval (Union[float, int]): The time interval (in seconds) for readiness or checks. 
        '''
        pass

    @abstractmethod
    def get_execution_id(self) -> str:
        '''
        Retrieves the execution ID of the task.

        This method returns the unique identifier associated with the task's execution. 
        The execution ID is crucial for tracking, logging, and differentiating between 
        multiple instances or runs of the same task.

        Returns:
            str: The unique execution ID of the task.
        '''
        pass

    @abstractmethod
    def get_icon(self) -> str:
        '''
        Retrieves the icon identifier of the current task.

        This method is used to get the icon associated with the task, which can be utilized for 
        visual representation in user interfaces or documentation.

        Returns:
            str: A string representing the icon identifier for the task
        '''
        pass

    @abstractmethod
    def get_color(self) -> str:
        '''
        Retrieves the color associated with the current task.

        This method returns the color of the task, useful for visual differentiation, priority indication, 
        or categorization in user interfaces or documentation.

        Returns:
            str: A string representing the color assigned to the task.
        '''
        pass

    @abstractmethod
    def get_description(self) -> str:
        '''
        Fetches the current description of the task.

        This method is used to obtain the detailed description of the task, providing insights into its purpose, 
        functionality, and usage within the task management system.

        Returns:
            str: The description of the task.
        '''
        pass

    @abstractmethod
    def get_cli_name(self) -> str:
        '''
        Gets the command-line interface (CLI) name of the task.

        This method returns the name used to invoke the task via a CLI, facilitating integration with command-line tools 
        or scripts.

        Returns:
            str: The CLI name of the task.
        '''
        pass

    @abstractmethod
    def _get_full_cli_name(self) -> str:
        '''
        Retrieves the full command-line interface (CLI) name of the task.

        Intended for internal use, this method provides the complete CLI name, including any 
        prefixes or namespaces, used primarily for logging or debugging purposes.

        Returns:
            str: The full CLI name of the task.
        '''
        pass

    @abstractmethod
    def _set_has_cli_interface(self):
        '''
        Marks the task as having a CLI interface.

        This internal method is used to indicate that the task is accessible and executable through a CLI, 
        enabling the task system to appropriately handle its CLI interactions.
        '''
        pass

    @abstractmethod
    def inject_env_files(self):
        '''
        Injects additional `EnvFile` into the task.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     def inject_env_files(self):
            >>>         self.add_env_files(EnvFile(path='config.env'))
        '''
        pass

    @abstractmethod
    def _get_env_files(self) -> List[EnvFile]:
        '''
        Retrieves the list of environment variable files associated with the task.

        Intended for internal use, this method returns a list of `EnvFile` instances that the task 
        uses to load environment variables, primarily for setup and configuration purposes.

        Returns:
            List[EnvFile]: A list of `EnvFile` instances associated with the task.
        '''
        pass

    @abstractmethod
    def inject_envs(self):
        '''
        Injects environment variables into the task.

        Example:
            >>> from zrb import Task
            >>> class MyTask(Task):
            >>>     def inject_envs(self):
            >>>         self.add_envs(Env(name='DATABASE_URL'))
        '''
        pass

    @abstractmethod
    def _get_envs(self) -> List[Env]:
        '''
        Retrieves the list of environment variables set for the task.

        For internal use, this method returns a list of `Env` instances representing the environment variables 
        configured for the task, essential for understanding and debugging the task's environment setup.

        Returns:
            List[Env]: A list of `Env` instances representing the environment variables of the task.
        '''
        pass

    @abstractmethod
    def inject_inputs(self):
        pass

    @abstractmethod
    def _get_inputs(self) -> List[AnyInput]:
        pass

    @abstractmethod
    def inject_checkers(self):
        pass

    @abstractmethod
    def _get_checkers(self) -> Iterable[TAnyTask]:
        pass

    @abstractmethod
    def inject_upstreams(self):
        pass

    @abstractmethod
    def _get_upstreams(self) -> Iterable[TAnyTask]:
        pass

    @abstractmethod
    def _get_combined_inputs(self) -> Iterable[AnyInput]:
        pass

    @abstractmethod
    def log_debug(self, message: Any):
        pass

    @abstractmethod
    def log_warn(self, message: Any):
        pass

    @abstractmethod
    def log_info(self, message: Any):
        pass

    @abstractmethod
    def log_error(self, message: Any):
        pass

    @abstractmethod
    def log_critical(self, message: Any):
        pass

    @abstractmethod
    def print_out(self, message: Any, trim_message: bool = True):
        pass

    @abstractmethod
    def print_err(self, message: Any, trim_message: bool = True):
        pass

    @abstractmethod
    def print_out_dark(self, message: Any, trim_message: bool = True):
        pass

    @abstractmethod
    def get_input_map(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def get_env_map(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def render_any(
        self, val: Any, data: Optional[Mapping[str, Any]] = None
    ) -> Any:
        pass

    @abstractmethod
    def render_float(
        self,
        val: Union[JinjaTemplate, float],
        data: Optional[Mapping[str, Any]] = None
    ) -> float:
        pass

    @abstractmethod
    def render_int(
        self,
        val: Union[JinjaTemplate, int],
        data: Optional[Mapping[str, Any]] = None
    ) -> int:
        pass

    @abstractmethod
    def render_bool(
        self, 
        val: Union[JinjaTemplate, bool],
        data: Optional[Mapping[str, Any]] = None
    ) -> bool:
        pass

    @abstractmethod
    def render_str(
        self,
        val: JinjaTemplate,
        data: Optional[Mapping[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def render_file(
        self,
        location: JinjaTemplate,
        data: Optional[Mapping[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def _run_all(self, *args: Any, **kwargs: Any) -> Any:
        '''
        For internal use
        '''
        pass

    @abstractmethod
    def _loop_check(self, show_info: bool) -> bool:
        '''
        For internal use
        '''
        pass

    @abstractmethod
    def _set_keyval(self, kwargs: Mapping[str, Any], env_prefix: str):
        '''
        For internal use
        '''
        pass

    @abstractmethod
    def _print_result(self, result: Any):
        '''
        For internal use
        '''
        pass

    @abstractmethod
    def print_result(self, result: Any):
        '''
        Outputs the task result to stdout for further processing.

        Override this method in subclasses to customize how the task result is displayed 
        or processed. Useful for integrating the task output with other systems or 
        command-line tools.

        Args:
            result (Any): The result of the task to be printed.

        Example:
            >> from zrb import Task
            >> # Example of overriding in a subclass
            >> class MyTask(Task):
            >>    def print_result(self, result: Any):
            >>        print(f'Result: {result}')
        '''
        pass
