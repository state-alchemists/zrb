import os

from zrb import load_file

_DIR = os.path.dirname(__file__)

assert load_file
load_file(os.path.join(_DIR, "fastapp", "_zrb", "zrb_init.py"))
