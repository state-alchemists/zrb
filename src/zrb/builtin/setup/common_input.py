from zrb.input.bool_input import BoolInput
from zrb.input.option_input import OptionInput

package_manager_input = OptionInput(
    name="package-manager",
    description="Your package manager",
    prompt="Your package manager",
    options=["apt", "dnf", "pacman", "zypper", "pkg", "brew", "spack"],
    default_str="apt",
)

use_sudo_input = BoolInput(
    name="use-sudo",
    description="Use sudo or not",
    prompt="Need sudo",
    default_str="yes",
)

setup_bash_input = BoolInput(
    name="setup-bash",
    description="Setup bash",
    prompt="Setup bash",
    default_str="yes",
)

setup_zsh_input = BoolInput(
    name="setup-zsh", description="Setup zsh", prompt="Setup zsh", default_str="yes"
)

setup_powershell_input = BoolInput(
    name="setup-powershell",
    description="Setup powershell",
    prompt="Setup powershell",
    default_str="no",
)
