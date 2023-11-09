🔖 [Table of Contents](../README.md) / [Tutorials](README.md)


# Extending CmdTask: Sending Message to Slack

```python
from typing import Any, Optional, Iterable, Union, Callable
from zrb import (
    runner, Group, AnyTask, CmdTask, AnyInput, StrInput, Env, EnvFile
)

import jsons
import os


class SlackPrintTask(CmdTask):

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        slack_channel_id: str = '',
        slack_app_token: str = '',
        message: str = '',
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
    ):
        CmdTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            should_execute=should_execute
        )
        self._slack_channel_id = slack_channel_id
        self._slack_app_token = slack_app_token
        self._message = message

    def inject_envs(self):
        self.add_envs(
            Env(
                name='CHANNEL_ID', os_name='',
                default=self.render_str(self._slack_channel_id)
            ),
            Env(
                name='TOKEN', os_name='',
                default=self.render_str(self._slack_app_token)
            ),
            Env(
                name='MESSAGE', os_name='',
                default=self.render_str(self._message)
            )
        )

    def get_cmd_script(self, *args: Any, **kwargs: Any):
        # contruct json payload and replace all `"` with `\\"`
        json_payload = jsons.dumps({
            'channel': '$CHANNEL_ID',
            'blocks': [{
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': '$MESSAGE'
                }
            }]
        }).replace('"', '\\"')
        # send payload to slack API
        return ' '.join([
            'curl -H "Content-type: application/json"',
            f'--data "{json_payload}"',
            '-H "Authorization: Bearer $TOKEN"',
            '-X POST https://slack.com/api/chat.postMessage'
        ])


say_hi = SlackPrintTask(
    name='say-hi',
    inputs=[
        StrInput(name='message', default='Hello world')
    ],
    slack_channel_id=os.getenv('SLACK_CHANNEL_ID'),
    slack_app_token=os.getenv('SLACK_APP_TOKEN'),
    message='{{ input.message }}',
)
runner.register(say_hi)

```

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
