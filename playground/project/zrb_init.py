from zrb import load_file
import os

_DIR = os.path.dirname(__file__)

assert load_file
load_file(os.path.join(_DIR, "fastapp/_zrb/init.py"))
