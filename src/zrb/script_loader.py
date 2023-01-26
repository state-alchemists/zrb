import logging
import os
import importlib


def load_script(script_path: str):
    if os.path.isfile(script_path):
        logging.info(f'loading {script_path}')
        importlib.import_module(script_path)
