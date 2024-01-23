from zrb.builtin.devtool.devtool_install import (
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
    install_terraform,
    install_tmux,
    install_zsh,
)

assert install_gvm
assert install_pyenv
assert install_nvm
assert install_sdkman
assert install_pulumi
assert install_aws
assert install_gcloud
assert install_tmux
assert install_zsh
assert install_kubectl
assert install_helm
assert install_docker
assert install_terraform
assert install_helix
