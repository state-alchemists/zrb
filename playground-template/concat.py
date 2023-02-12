from .zrb_init import concat

import sys

main_loop = concat.create_main_loop()
main_loop(*sys.argv)