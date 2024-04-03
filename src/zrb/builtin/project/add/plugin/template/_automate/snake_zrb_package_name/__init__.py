import os
import sys

from ._group import snake_zrb_package_name_group
from .build import build_snake_zrb_package_name
from .prepare_venv.prepare_venv import prepare_snake_zrb_package_name_venv
from .publish.publish import publish_snake_zrb_package_name

_CURRENT_DIR = os.path.dirname(__file__)
_AUTOMATE_DIR = os.path.dirname(_CURRENT_DIR)
_PROJECT_DIR = os.path.dirname(_AUTOMATE_DIR)
_PLUGIN_SRC_DIR = os.path.join(_PROJECT_DIR, "src", "kebab-zrb-package-name", "src")
if os.path.isdir(_PLUGIN_SRC_DIR):
    sys.path.append(_PLUGIN_SRC_DIR)
    import snake_zrb_package_name

    assert snake_zrb_package_name

assert snake_zrb_package_name_group
assert build_snake_zrb_package_name
assert prepare_snake_zrb_package_name_venv
assert publish_snake_zrb_package_name
