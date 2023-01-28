from ..action.base_action import BaseAction
from ..task.base_task import BaseTask

import click
import asyncio


class Runner(BaseAction):

    def serve(self, cli: click.core.Group) -> click.core.Group:
        for task in self.tasks:
            '''
            We want to use click this way:

            @click.command(name='subcommand')
            @click.option('--one', 'one', default='one', prompt='First')
            @click.option('--two', 'two', default='two', prompt='Two')
            def my_function(one, two):
                print(one, two)
            cli.add_command(my_function)

            But since we need to do this for every task and inputs,
            we need to modify code a little bit:

            def my_function(one, two):
                print(one, two)
            runner = click.command(name='subcommand')(runner)
            runner = click.option(
                '--one', 'one', default='one', prompt='First')(runner)
            runner = click.option(
                '--two', 'two', default='two', prompt='Two')(my_function)
            cli.add_command(runner)

            That was what we do here.
            '''
            task_inputs = task.get_inputs()
            runner = self._get_task_runner(task)
            runner = click.command(name=task.get_name())(runner)
            for task_input in task_inputs:
                args = task_input.get_args()
                kwargs = task_input.get_kwargs()
                runner = click.option(*args, **kwargs)(runner)
            cli.add_command(runner)
        return cli

    def _get_task_runner(self, task: BaseTask):
        def runner(*args, **kwargs):
            async_runner = self._get_async_task_runner(task)
            asyncio.run(async_runner(*args, **kwargs))
        return runner

    def _get_async_task_runner(self, task: BaseTask):
        async def async_runner(*args, **kwargs):
            await asyncio.gather(*[
                task._run(*args, **kwargs),
                task._check()
            ])
        return async_runner
