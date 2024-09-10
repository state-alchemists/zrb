import json
import os
from collections.abc import Mapping

PROJECT_DIR = os.getenv("ZRB_PROJECT_DIR", ".")
MONOREPO_CONFIG_FILE = os.path.join(PROJECT_DIR, "monorepo.zrb.json")
MONOREPO_CONFIG: Mapping[str, Mapping[str, str]] = {}

if os.path.isfile(MONOREPO_CONFIG_FILE):
    with open(MONOREPO_CONFIG_FILE, "r") as file:
        MONOREPO_CONFIG = json.load(file)
