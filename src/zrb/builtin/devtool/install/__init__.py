from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.builtin.devtool.install.aws.aws import install_aws
from zrb.builtin.devtool.install.docker.docker import install_docker
from zrb.builtin.devtool.install.gcloud.gcloud import install_gcloud
from zrb.builtin.devtool.install.gvm.gvm import install_gvm
from zrb.builtin.devtool.install.helix.helix import install_helix
from zrb.builtin.devtool.install.helm.helm import install_helm
from zrb.builtin.devtool.install.kubectl.kubectl import install_kubectl
from zrb.builtin.devtool.install.nvm.nvm import install_nvm
from zrb.builtin.devtool.install.pulumi.pulumi import install_pulumi
from zrb.builtin.devtool.install.pyenv.pyenv import install_pyenv
from zrb.builtin.devtool.install.sdkman.sdkman import install_sdkman
from zrb.builtin.devtool.install.selenium.selenium import install_selenium
from zrb.builtin.devtool.install.terraform.terraform import install_terraform
from zrb.builtin.devtool.install.tmux.tmux import install_tmux
from zrb.builtin.devtool.install.zsh.zsh import install_zsh

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
