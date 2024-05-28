🔖 [Table of Contents](../README.md) / [Concepts and Terminologies](README.md)

# Extending Task

There are some methods you need to know whenever you decide to extend a Task.

- `run(self, *args: Any, **kwargs: Any) -> Any`: Actions to do when the task is started.
- `check(self) -> bool`: Actions to confirm whether a Task is ready.
- `inject_env_files(self)`: Actions to add environment files.
- `inject_envs(self)`: Actions to add environments.
- `inject_inputs(self)`: Actions to add inputs.
- `inject_checkers(self)`: Actions to add checkers.
- `inject_upstreams(self)`: Actions to add upstreams.
- `print_result(self, result: Any)`: Define how to print Task execution result.

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


Let's see some examples.

## DDGSearchTask

In this example, we want to create a Task to search from DuckDuckGo.

For this, we should first install `duckduckgo-search`.

```bash
pip install duckduckgo-search
```

The task should have two additional properties:

- max_results
- keyword

We also want to print the result beautifully.

Let's define a `DDGSearchTask`.

```python
from zrb import (
    runner, Task, AnyTask, Env, EnvFile, Group, AnyInput, StrInput, IntInput,
    OnFailed, OnReady, OnRetry, OnSkipped, OnStarted, OnTriggered, OnWaiting
)
from zrb.helper.typing import (
    Any, Callable, Iterable, List, Mapping, JinjaTemplate
)
from zrb.helper.typecheck import typechecked
from duckduckgo_search import DDGS


@typechecked
class DDGSearchTask(Task):
    def __init__(
        self,
        name: str,
        group: Group | None = None,
        description: str = '',
        inputs: List[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: str | None = None,
        color: str | None = None,
        retry: int = 2,
        retry_interval: float | int = 1,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: float | int = 0,
        run: Callable[..., Any] | None = None,
        on_triggered: OnTriggered | None = None,
        on_waiting: OnWaiting | None = None,
        on_skipped: OnSkipped | None = None,
        on_started: OnStarted | None = None,
        on_ready: OnReady | None = None,
        on_retry: OnRetry | None = None,
        on_failed: OnFailed | None = None,
        should_execute: bool | str | Callable[..., bool] = True,
        return_upstream_result: bool = False,
        max_results: JinjaTemplate | int = 5,
        keyword: JinjaTemplate = ''
    ):
        super().__init__(
            name=name,
            group=group,
            description=description,
            inputs=inputs,
            envs=envs,
            env_fiels=env_files,
            icon=icon,
            color=color,
            retry=retry,
            retry_interval=retry_interval,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            run=run,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result
        )
        self._max_results = max_results
        self._keyword = keyword

    def run(self, *args: Any, **kwargs: Any) -> List[Mapping[str, str]]:
        # keyword and max results can be Jinja Template,
        # we need to render them.
        keyword = self.render_str(self._keyword)
        max_results = self.render_int(self._max_results)
        # Get the result (it should be a list of dictionary)
        with DDGS() as ddgs:
            results = [
                r for r in ddgs.text(keyword, max_results=max_results)
            ]
            return results

    def print_result(self, result: Any):
        lines = ['Result:']
        for r in result:
            # Add title
            title = r.get('title', 'No Title')
            lines.append(f'# {title}')
            # Add URL
            href = r.get('href', 'No Link')
            lines.append(f'URL: {href}')
            # Add Body
            body = r.get('body', 'No Result')
            lines.append('')
            lines.append(body)
            lines.append('')
        self.print_out('\n'.join(lines))
```

Here is how you can use `DDGSearchTask`:

```python
search = DDGSearchTask(
    name='search',
    inputs=[
        StrInput(name='keyword', default='hakuna matata'),
        IntInput(name='max-results', default=5)
    ],
    max_results='{{ input.max_results }}',
    keyword='{{ input.keyword }}'
)
runner.register(search)
```

You can run the Task by invoking the following command.

```bash
zrb search
```

The output is as follows:

```
Keyword [hakuna matata]:
Max results [5]:
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2024-01-21 15:55:22.950 ❁  41929 → 1/3 🐹          zrb search • Completed in 1.3078629970550537 seconds
🤖 ○ ◷ 2024-01-21 15:55:22.950 ❁  41929 → 1/3 🐹          zrb search • Result:
# Hakuna matata - Wikipedia
URL: https://en.wikipedia.org/wiki/Hakuna_matata

The Lion King song In 1994, the Walt Disney Feature Animation animated film The Lion King brought the phrase international recognition, featuring it prominently in the plot and devoting a song to it. A meerkat and a warthog, Timon and Pumbaa, teach Simba that he should forget his troubled past and live in the present.

# Hakuna Matata (From "The Lion King") - YouTube
URL: https://www.youtube.com/watch?v=0MxulhivCvI

Hakuna Matata (From "The Lion King") - YouTube 0:00 / 4:43 Hakuna Matata (From "The Lion King") DisneyMusicVEVO 34M subscribers Subscribe Subscribed 475K Share 80M views 3 years ago...

# Hakuna Matata | The Lion King 1994 - YouTube
URL: https://www.youtube.com/watch?v=nbY_aP-alkw

Lyrics: Hakuna Matata, what a wonderful phrase ...more ...more Try YouTube Kids Learn more Movie The Lion King Lyrics:Hakuna Matata, what a wonderful phraseHakuna Matata, ain't no passing...

# Hakuna Matata (song) - Wikipedia
URL: https://en.wikipedia.org/wiki/Hakuna_Matata_(song)

Meaning Hakuna matata is a phrase in Swahili that is frequently translated as "no worries". In a behind-the-scenes segment on The Lion King Special Edition DVD, the film's production team claim that it picked up the term from a tour guide while on safari in Kenya.

# Hakuna Matata - Disney's THE LION KING (Official Lyric Video)
URL: https://www.youtube.com/watch?v=D4zG1Tnt5A8

Sandra Klein 310K views 3 years ago The Lion King (Musical) Trailer (1997) | StarLion production Star Lion Blog 38K views 5 years ago Hakuna Matata Lebo M - Topic 287K views 5 years ago Queen -...
To run again: zrb search --keyword "hakuna matata" --max-results "5"
```

# TODO

Add more examples.

# Next

Next you can see how you can [extend CmdTask](extending-cmd-task.md).

🔖 [Table of Contents](../README.md) / [Concepts and Terminologies](README.md)
