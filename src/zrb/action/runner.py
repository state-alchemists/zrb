from ..action.base_action import BaseAction
import click


class Runner(BaseAction):
    env_prefix: str = ''

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
            task_inputs = task.get_all_inputs()
            task_cmd_name = task.get_cmd_name()
            task_main_loop = task.create_main_loop(env_prefix=self.env_prefix)
            runner = click.command(name=task_cmd_name)(task_main_loop)
            for task_input in task_inputs:
                args = task_input.get_args()
                kwargs = task_input.get_kwargs()
                runner = click.option(*args, **kwargs)(runner)
            cli.add_command(runner)
        return cli
