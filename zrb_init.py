from typing import Any
from collections.abc import Mapping
from zrb import (
    runner,
    AnyTask,
    python_task,
    Task,
    CmdTask,
    DockerComposeTask,
    FlowTask,
    Checker,
    ResourceMaker,
    RsyncTask,
    RemoteCmdTask,
    PathChecker,
    PathWatcher,
    TimeWatcher,
    PortChecker,
    HTTPChecker,
    Server,
    Notifier,
    Env,
    EnvFile,
    Group,
    AnyInput,
    Input,
    BoolInput,
    ChoiceInput,
    FloatInput,
    IntInput,
    MultilineInput,
    PasswordInput,
    StrInput,
)
from zrb.task.base_task.base_task import BaseTask
from zrb.task_input.base_input import BaseInput
from zrb.helper.docstring import get_markdown_from_docstring

import os
import re
import sys
import tomlkit

_CURRENT_DIR = os.path.dirname(__file__)
_PLAYGROUND_DIR = os.path.join(_CURRENT_DIR, "playground")
_IS_PLAYGROUND_EXIST = os.path.isfile(os.path.join(_PLAYGROUND_DIR, "zrb_init.py"))

if _IS_PLAYGROUND_EXIST:
    sys.path.append(_PLAYGROUND_DIR)
    from playground import zrb_init as playground_init
    assert playground_init


with open(os.path.join(_CURRENT_DIR, "pyproject.toml"), "rb") as f:
    toml_dict = tomlkit.parse(f.read())
    VERSION = toml_dict["tool"]["poetry"]["version"]


def inject_doc(markdown_file_name: str, cls):
    docstring_markdown = get_markdown_from_docstring(cls)
    with open(markdown_file_name, "r") as file:
        original_content = file.read()
    pattern = r"<!--start-doc-->.*?<!--end-doc-->"
    replacement_text = "\n".join(
        [
            "<!--start-doc-->",
            docstring_markdown,
            "<!--end-doc-->",
        ]
    )
    new_content = re.sub(pattern, replacement_text, original_content, flags=re.DOTALL)
    with open(markdown_file_name, "w") as file:
        file.write(new_content)


###############################################################################
# Group Definitions
###############################################################################

playground_group = Group(name="playground", description="Playground related tasks")

###############################################################################
# 🔤 Input Definitions
###############################################################################

zrb_version_input = StrInput(
    name="zrb-version", description="Zrb version", prompt="Zrb version", default=VERSION
)

zrb_image_name_input = StrInput(
    name="zrb-image-name",
    description="Zrb image name",
    prompt="Zrb image name",
    default=f"docker.io/stalchmst/zrb:{VERSION}",
)

zrb_latest_image_name_input = StrInput(
    name="zrb-latest-image-name",
    description="Zrb latest image name",
    prompt="Zrb latest image name",
    default="docker.io/stalchmst/zrb:latest",
)

build_zrb_input = BoolInput(name="build-zrb", default=True)
install_symlink_input = BoolInput(name="install-symlink", default=True)
create_playground_input = BoolInput(
    name="create-playground", default=not _IS_PLAYGROUND_EXIST
)

###############################################################################
# 🌱 Env Definitions
###############################################################################

zrb_version_env = Env(name="ZRB_VERSION", os_name="", default="{{input.zrb_version}}")

zrb_image_env = Env(name="ZRB_IMAGE", os_name="", default="{{input.zrb_image_name}}")

zrb_latest_image_env = Env(
    name="ZRB_IMAGE", os_name="", default="{{input.zrb_latest_image_name}}"
)


###############################################################################
# ⚙️ format-code
###############################################################################

format_code = CmdTask(
    name="format-code",
    description="Format code",
    cwd=_CURRENT_DIR,
    cmd=[
        "isort src",
        "black src",
    ],
    should_print_cmd_result=False,
)
runner.register(format_code)


###############################################################################
# ⚙️ make-docs
###############################################################################


@python_task(
    name="make-docs",
    description="Make documentation",
    upstreams=[format_code],
    runner=runner,
)
def make_docs(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    dir = os.path.join(_CURRENT_DIR, "docs", "technical-documentation")
    configs: Mapping[str, Any] = {
        os.path.join(dir, "task-group.md"): Group,
        os.path.join(dir, "task-envs", "env.md"): Env,
        os.path.join(dir, "task-envs", "env-file.md"): EnvFile,
        os.path.join(dir, "tasks", "any-task.md"): AnyTask,
        os.path.join(dir, "tasks", "base-task.md"): BaseTask,
        os.path.join(dir, "tasks", "task.md"): Task,
        os.path.join(dir, "tasks", "checker.md"): Checker,
        os.path.join(dir, "tasks", "cmd-task.md"): CmdTask,
        os.path.join(dir, "tasks", "docker-compose-task.md"): DockerComposeTask,
        os.path.join(dir, "tasks", "flow-task.md"): FlowTask,
        os.path.join(dir, "tasks", "http-checker.md"): HTTPChecker,
        os.path.join(dir, "tasks", "path-checker.md"): PathChecker,
        os.path.join(dir, "tasks", "path-watcher.md"): PathWatcher,
        os.path.join(dir, "tasks", "port-checker.md"): PortChecker,
        os.path.join(dir, "tasks", "python-task.md"): python_task,
        os.path.join(dir, "tasks", "server.md"): Server,
        os.path.join(dir, "tasks", "remote-cmd-task.md"): RemoteCmdTask,
        os.path.join(dir, "tasks", "resource-maker.md"): ResourceMaker,
        os.path.join(dir, "tasks", "rsync-task.md"): RsyncTask,
        os.path.join(dir, "tasks", "notifier.md"): Notifier,
        os.path.join(dir, "tasks", "time-watcher.md"): TimeWatcher,
        os.path.join(dir, "task-inputs", "any-input.md"): AnyInput,
        os.path.join(dir, "task-inputs", "base-input.md"): BaseInput,
        os.path.join(dir, "task-inputs", "input.md"): Input,
        os.path.join(dir, "task-inputs", "bool-input.md"): BoolInput,
        os.path.join(dir, "task-inputs", "choice-input.md"): ChoiceInput,
        os.path.join(dir, "task-inputs", "float-input.md"): FloatInput,
        os.path.join(dir, "task-inputs", "int-input.md"): IntInput,
        os.path.join(dir, "task-inputs", "multiline-input.md"): MultilineInput,
        os.path.join(dir, "task-inputs", "password-input.md"): PasswordInput,
        os.path.join(dir, "task-inputs", "str-input.md"): StrInput,
    }
    for file_name, cls in configs.items():
        task.print_out(f"Inject `{cls.__name__} docstring` to {file_name}")
        inject_doc(file_name, cls)


###############################################################################
# ⚙️ build
###############################################################################

build = CmdTask(
    name="build",
    description="Build Zrb",
    upstreams=[make_docs],
    cwd=_CURRENT_DIR,
    cmd=[
        "set -e",
        'echo "🤖 Build zrb distribution"',
        f"rm -Rf {_CURRENT_DIR}/dist",
        "git add . -A",
        "poetry build",
    ],
)
skippable_build: CmdTask = build.copy()
skippable_build.add_input(build_zrb_input)
skippable_build.set_should_execute("{{ input.build_zrb}}")
runner.register(build)

###############################################################################
# ⚙️ publish-pip
###############################################################################

publish_pip = CmdTask(
    name="publish-pip",
    description="Publish zrb to pypi",
    upstreams=[build],
    cwd=_CURRENT_DIR,
    cmd=[
        "set -e",
        'echo "🤖 Publish zrb to pypi"',
        "poetry publish"
    ],
)
runner.register(publish_pip)

###############################################################################
# ⚙️ check-pip
###############################################################################

check_pip = HTTPChecker(
    name="check-pip",
    inputs=[zrb_version_input],
    is_https=True,
    host="pypi.org",
    url="pypi/zrb/{{ input.zrb_version }}/json",
    port=443,
)

###############################################################################
# ⚙️ build-image
###############################################################################

build_image = DockerComposeTask(
    name="build-image",
    description="Build docker image",
    upstreams=[check_pip],
    inputs=[
        zrb_version_input,
        zrb_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_image_env,
    ],
    cwd=f"{_CURRENT_DIR}/docker",
    compose_cmd="build",
    compose_args=["zrb"],
)
runner.register(build_image)

###############################################################################
# ⚙️ build-latest-image
###############################################################################

build_latest_image = DockerComposeTask(
    name="build-latest-image",
    description="Build docker image",
    upstreams=[
        check_pip,
        build_image,
    ],
    inputs=[
        zrb_version_input,
        zrb_latest_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_latest_image_env,
    ],
    cwd=f"{_CURRENT_DIR}/docker",
    compose_cmd="build",
    compose_args=["zrb"],
)
runner.register(build_latest_image)

###############################################################################
# ⚙️ stop-container
###############################################################################

stop_container = DockerComposeTask(
    name="stop-container",
    description="remove docker container",
    inputs=[zrb_image_name_input],
    envs=[zrb_image_env],
    cwd=f"{_CURRENT_DIR}/docker",
    compose_cmd="down",
)
runner.register(stop_container)

###############################################################################
# ⚙️ start-container
###############################################################################

start_container = DockerComposeTask(
    name="start-container",
    description="Run docker container",
    upstreams=[build_image, stop_container],
    inputs=[
        zrb_version_input,
        zrb_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_image_env,
    ],
    cwd=f"{_CURRENT_DIR}/docker",
    compose_cmd="up",
    compose_flags=["-d"],
)
runner.register(start_container)

###############################################################################
# ⚙️ push-image
###############################################################################

push_image = DockerComposeTask(
    name="push-image",
    description="Push docker image",
    upstreams=[build_image],
    inputs=[
        zrb_version_input,
        zrb_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_image_env,
    ],
    cwd=f"{_CURRENT_DIR}/docker",
    compose_cmd="push",
    compose_args=["zrb"],
)
runner.register(push_image)

###############################################################################
# ⚙️ push-latest-image
###############################################################################

push_latest_image = DockerComposeTask(
    name="push-latest-image",
    description="Push docker image",
    upstreams=[
        build_latest_image,
        push_image,
    ],
    inputs=[
        zrb_version_input,
        zrb_latest_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_latest_image_env,
    ],
    cwd=f"{_CURRENT_DIR}/docker",
    compose_cmd="push",
    compose_args=["zrb"],
)
runner.register(push_latest_image)

###############################################################################
# ⚙️ publish
###############################################################################

publish = FlowTask(
    name="publish",
    description="Publish new version",
    steps=[
        publish_pip,
        push_latest_image,
    ],
)
runner.register(publish)

###############################################################################
# ⚙️ install-symlink
###############################################################################

install_symlink = CmdTask(
    name="install-symlink",
    description="Install Zrb as symlink",
    upstreams=[skippable_build],
    cmd=[
        "set -e",
        f"cd {_CURRENT_DIR}",
        'echo "🤖 Install zrb"',
        "poetry install",
    ],
)
skippable_install_symlink: CmdTask = install_symlink.copy()
skippable_install_symlink.add_input(build_zrb_input, install_symlink_input)
skippable_install_symlink.set_should_execute("{{ input.install_symlink}}")
runner.register(install_symlink)

###############################################################################
# ⚙️ test
###############################################################################

test_only = CmdTask(
    name="test",
    description="Run zrb test",
    inputs=[
        StrInput(
            name="test",
            shortcut="t",
            description="Specific test case (i.e., test/file.py::test_name)",
            prompt="Test (i.e., test/file.py::test_name)",
            default="",
        ),
    ],
    cmd=[
        "set -e",
        'echo "🤖 Perform test"',
        "pytest -vv \\",
        '  --ignore-glob="**/template/**/test" \\',
        '  --ignore-glob="**/generator/**/app"  \\',
        '  --ignore-glob="**/builtin/project/**/template"  \\',
        "  --ignore=playground \\",
        "  --cov=zrb \\",
        '  --cov-config=".coveragerc" \\',
        "  --cov-report=html \\",
        "  --cov-report=term \\",
        "  --cov-report=term-missing {{input.test}}",
    ],
    retry=0,
    checking_interval=1,
    should_print_cmd_result=False,
)

test = test_only.copy()
test.add_upstream(install_symlink)
runner.register(test)

###############################################################################
# ⚙️ serve-test
###############################################################################

serve_test = CmdTask(
    name="serve-test",
    description="Serve zrb test result",
    inputs=[
        StrInput(
            name="port",
            shortcut="p",
            description="Port to serve coverage result",
            prompt="Serve coverage on port",
            default="9000",
        )
    ],
    upstreams=[test],
    cmd=[
        "set -e",
        'echo "🤖 Serve coverage report"',
        "python -m http.server {{input.port}} \\",
        f'  --directory "{_CURRENT_DIR}/htmlcov"',
    ],
    checkers=[HTTPChecker(port="{{input.port}}")],
    retry=0,
    checking_interval=0.3,
)
runner.register(serve_test)

###############################################################################
# ⚙️ playground create
###############################################################################

create_playground = CmdTask(
    name="create",
    description="Create playground",
    group=playground_group,
    upstreams=[skippable_install_symlink],
    cwd=_CURRENT_DIR,
    cmd_path=os.path.join(_CURRENT_DIR, "playground-create.sh"),
    retry=0,
    preexec_fn=None,
    should_print_cmd_result=False,
)
runner.register(create_playground)

###############################################################################
# ⚙️ prepare-profile
###############################################################################

prepare_profile = CmdTask(
    name="prepare-profile",
    description="Prepare profile",
    cmd="python -m cProfile -o .cprofile.prof $(pwd)/src/zrb/__main__.py",
    # cmd='python -m cProfile -o .cprofile.prof -m zrb',
    retry=0,
)

###############################################################################
# ⚙️ profile
###############################################################################

profile = CmdTask(
    name="profile",
    description="Visualize profile",
    upstreams=[prepare_profile],
    cmd="flameprof .cprofile.prof > .cprofile.svg",
    retry=0,
)
runner.register(profile)
