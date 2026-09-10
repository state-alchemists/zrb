import sys

from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.option_input import OptionInput


def get_default_package_manager(_: AnyContext) -> str:
    # macOS has no apt/dnf/pacman/zypper/pkg; brew is the only sane default.
    return "brew" if sys.platform == "darwin" else "apt"


def get_default_use_sudo(_: AnyContext) -> bool:
    # brew must run unprivileged: `sudo brew` corrupts its directory permissions.
    return sys.platform != "darwin"


package_manager_input = OptionInput(
    name="package-manager",
    description="Your package manager",
    prompt="Your package manager",
    options=["apt", "dnf", "pacman", "zypper", "pkg", "brew", "spack"],
    default=get_default_package_manager,
)

use_sudo_input = BoolInput(
    name="use-sudo",
    description="Use sudo or not",
    prompt="Need sudo",
    default=get_default_use_sudo,
)

setup_bash_input = BoolInput(
    name="setup-bash",
    description="Setup bash",
    prompt="Setup bash",
    default=True,
)

setup_zsh_input = BoolInput(
    name="setup-zsh", description="Setup zsh", prompt="Setup zsh", default=True
)

setup_powershell_input = BoolInput(
    name="setup-powershell",
    description="Setup powershell",
    prompt="Setup powershell",
    default=False,
)
