import os

from zrb.config.config import CFG


def get_init_path_list() -> list[str]:
    current_path = os.path.abspath(os.getcwd())
    dir_path_list = [current_path]
    while current_path != os.path.dirname(current_path):  # Stop at root
        current_path = os.path.dirname(current_path)
        dir_path_list.append(current_path)
    zrb_init_path_list = []
    for current_path in dir_path_list[::-1]:
        zrb_init_path = os.path.join(current_path, CFG.INIT_FILE_NAME)
        CFG.LOGGER.info(f"Finding {zrb_init_path}")
        if os.path.isfile(zrb_init_path):
            zrb_init_path_list.append(zrb_init_path)
    return zrb_init_path_list
