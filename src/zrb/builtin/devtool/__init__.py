from zrb.builtin.devtool._group import devtool_group
from zrb.builtin.devtool.install import (
    devtool_install_group,
    install_aws,
    install_docker,
    install_gcloud,
    install_gvm,
    install_helix,
    install_helm,
    install_kubectl,
    install_nvm,
    install_pulumi,
    install_pyenv,
    install_sdkman,
    install_selenium,
    install_terraform,
    install_tmux,
    install_zsh,
)

assert devtool_group
assert devtool_install_group
assert install_aws
assert install_docker
assert install_gcloud
assert install_gvm
assert install_helix
assert install_helm
assert install_kubectl
assert install_nvm
assert install_pulumi
assert install_pyenv
assert install_sdkman
assert install_selenium
assert install_terraform
assert install_tmux
assert install_zsh
