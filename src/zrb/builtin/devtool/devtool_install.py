import os

from zrb.builtin.group import dev_tool_install_group
from zrb.config.config import get_current_shell
from zrb.helper.file.text import read_text_file_async, write_text_file_async
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task
from zrb.task_input.bool_input import BoolInput
from zrb.task_input.str_input import StrInput

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "..", "shell-scripts")
current_shell = get_current_shell()

###############################################################################
# 🔤 Input Definitions
###############################################################################

terminal_config_file_input = StrInput(
    name="config-file",
    shortcut="c",
    prompt="Config file",
    default="~/.zshrc" if current_shell == "zsh" else "~/.bashrc",
)

###############################################################################
# Helper Definitions
###############################################################################


@typechecked
def write_config(
    template_file: str, config_file: str, remove_old_config: bool = False
) -> Callable[..., Any]:
    async def set_config(*args, **kwargs):
        task: Task = kwargs.get("_task")
        rendered_config_file = os.path.expandvars(
            os.path.expanduser(task.render_str(config_file))
        )
        rendered_template_file = os.path.expandvars(
            os.path.expanduser(task.render_str(template_file))
        )
        if remove_old_config and os.path.exists(rendered_config_file):
            task.print_out(f"Removing {rendered_config_file}")
            os.remove(rendered_config_file)
        additional_content = await read_text_file_async(rendered_template_file)
        content = ""
        if os.path.exists(rendered_config_file):
            content = await read_text_file_async(rendered_config_file) + "\n"
        new_content = content + additional_content
        task.print_out(f"Writing content to {rendered_config_file}")
        await write_text_file_async(rendered_config_file, new_content)

    return set_config


###############################################################################
# Task Definitions
###############################################################################

install_gvm = FlowTask(
    name="gvm",
    group=dev_tool_install_group,
    description="GVM provides interface to manage go version",
    inputs=[
        StrInput(
            name="go-default-version",
            description="Go default version",
            default="go1.21",
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-gvm",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "gvm", "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-gvm",
            run=write_config(
                template_file=os.path.join(CURRENT_DIR, "gvm", "resource", "config.sh"),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-gvm-installation",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "gvm", "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_gvm)

install_pyenv = FlowTask(
    name="pyenv",
    group=dev_tool_install_group,
    description="Simple Python version management",
    inputs=[
        StrInput(
            name="python-default-version",
            description="Python default version",
            default="3.10.0",
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-pyenv",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "pyenv", "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-pyenv",
            run=write_config(
                template_file=os.path.join(
                    CURRENT_DIR, "pyenv", "resource", "config.sh"
                ),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-pyenv-installation",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "pyenv", "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_pyenv)

install_nvm = FlowTask(
    name="nvm",
    group=dev_tool_install_group,
    description="NVM allows you to quickly install and use different versions of node via the command line",  # noqa
    inputs=[
        StrInput(
            name="node-default-version",
            description="Node default version",
            default="node",
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-nvm",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "nvm", "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-nvm",
            run=write_config(
                template_file=os.path.join(CURRENT_DIR, "nvm", "resource", "config.sh"),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-nvm-installation",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "nvm", "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_nvm)

install_sdkman = FlowTask(
    name="sdkman",
    group=dev_tool_install_group,
    description="SDKMAN! is a tool for managing parallel versions of multiple Software Development Kits on most Unix based systems",  # noqa
    inputs=[
        BoolInput(
            name="install-java",
            description="Install Java",
            prompt="Do you want to install Java?",
            default=True,
        ),
        BoolInput(
            name="install-scala",
            description="Install Scala",
            prompt="Do you want to install Scala?",
            default=True,
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-sdkman",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "sdkman", "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-sdkman",
            run=write_config(
                template_file=os.path.join(
                    CURRENT_DIR, "sdkman", "resource", "config.sh"
                ),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-sdkman-installation",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "sdkman", "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_sdkman)

install_pulumi = FlowTask(
    name="pulumi",
    group=dev_tool_install_group,
    description="Universal infrastructure as code",
    inputs=[terminal_config_file_input],
    steps=[
        CmdTask(
            name="install-pulumi",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "pulumi", "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-pulumi",
            run=write_config(
                template_file=os.path.join(
                    CURRENT_DIR, "pulumi", "resource", "config.sh"
                ),
                config_file="{{input.config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_pulumi)

install_aws = FlowTask(
    name="aws",
    group=dev_tool_install_group,
    description="AWS CLI",
    steps=[
        CmdTask(
            name="install-aws",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "aws", "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_aws)

install_gcloud = FlowTask(
    name="gcloud",
    group=dev_tool_install_group,
    description="Gcloud CLI",
    steps=[
        CmdTask(
            name="install-gcloud",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "gcloud", "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_gcloud)

install_tmux = FlowTask(
    name="tmux",
    group=dev_tool_install_group,
    description="Terminal multiplexer",
    inputs=[
        StrInput(
            name="tmux-config-file",
            shortcut="c",
            prompt="Tmux config file",
            default="~/.tmux.conf",
        )
    ],
    steps=[
        CmdTask(
            name="install-tmux",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "tmux", "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-tmux",
            run=write_config(
                template_file=os.path.join(
                    CURRENT_DIR, "tmux", "resource", "config.sh"
                ),
                config_file="{{input.tmux_config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_tmux)

install_zsh = FlowTask(
    name="zsh",
    group=dev_tool_install_group,
    description="Zsh terminal + oh-my-zsh + zdharma",
    inputs=[
        StrInput(
            name="zsh-config-file",
            shortcut="c",
            prompt="Zsh config file",
            default="~/.zshrc",
        )
    ],
    steps=[
        CmdTask(
            name="install-zsh",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "zsh", "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-zsh",
            run=write_config(
                template_file=os.path.join(CURRENT_DIR, "zsh", "resource", "config.sh"),
                config_file="{{input.zsh_config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_zsh)

install_kubectl = FlowTask(
    name="kubectl",
    group=dev_tool_install_group,
    description="Kubernetes CLI tool",
    steps=[
        CmdTask(
            name="install-kubectl",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "kubectl", "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_kubectl)

install_helm = FlowTask(
    name="helm",
    group=dev_tool_install_group,
    description="Package manager for kubernetes",
    steps=[
        CmdTask(
            name="install-helm",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "helm", "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_helm)

install_docker = FlowTask(
    name="docker",
    group=dev_tool_install_group,
    description="Most popular containerization platform",
    steps=[
        CmdTask(
            name="install-docker",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "docker", "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_docker)

install_terraform = FlowTask(
    name="terraform",
    group=dev_tool_install_group,
    description="Open source IAC by Hashicorp",
    inputs=[terminal_config_file_input],
    steps=[
        CmdTask(
            name="install-terraform",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "terraform", "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-terraform",
            run=write_config(
                template_file=os.path.join(
                    CURRENT_DIR, "terraform", "resource", "config.sh"
                ),
                config_file="{{input.config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_terraform)

install_helix = FlowTask(
    name="helix",
    group=dev_tool_install_group,
    description="Post modern text editor",
    steps=[
        CmdTask(
            name="install-helix",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "helix", "install.sh"),
            ],
            preexec_fn=None,
        ),
        [
            Task(
                name="create-helix-theme",
                run=write_config(
                    template_file=os.path.join(
                        CURRENT_DIR,
                        "helix",
                        "resource",
                        "themes",
                        "gruvbox_transparent.toml",  # noqa
                    ),
                    config_file="~/.config/helix/themes/gruvbox_transparent.toml",  # noqa
                    remove_old_config=True,
                ),
            ),
            Task(
                name="configure-helix",
                run=write_config(
                    template_file=os.path.join(
                        CURRENT_DIR, "helix", "resource", "config.toml"
                    ),
                    config_file="~/.config/helix/config.toml",
                    remove_old_config=True,
                ),
            ),
            CmdTask(
                name="install-language-server",
                cmd_path=[
                    os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                    os.path.join(CURRENT_DIR, "helix", "install-language-server.sh"),
                ],
                preexec_fn=None,
            ),
        ],
    ],
    retry=0,
)
runner.register(install_helix)

install_selenium = FlowTask(
    name="selenium",
    group=dev_tool_install_group,
    description="Selenium + Chrome web driver",
    steps=[
        CmdTask(
            name="install-selenium",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "selenium", "install.sh"),
            ],
            preexec_fn=None,
        )
    ],
)
runner.register(install_selenium)
