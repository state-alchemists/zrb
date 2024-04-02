from zrb.builtin.ubuntu._group import ubuntu_group
from zrb.builtin.ubuntu.install import (
    install_ubuntu_all,
    install_ubuntu_essentials,
    install_ubuntu_tex,
    install_ubuntu_toys,
    ubuntu_install_group,
)
from zrb.builtin.ubuntu.update import update_ubuntu

assert ubuntu_group
assert ubuntu_install_group
assert update_ubuntu
assert ubuntu_install_group
assert install_ubuntu_all
assert install_ubuntu_essentials
assert install_ubuntu_tex
assert install_ubuntu_toys
