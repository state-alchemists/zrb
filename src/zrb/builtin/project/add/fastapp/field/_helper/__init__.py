from .inject_delete_page import inject_delete_page
from .inject_detail_page import inject_detail_page
from .inject_insert_page import inject_insert_page
from .inject_list_page import inject_list_page
from .inject_repo import inject_repo
from .inject_schema import inject_schema
from .inject_test import inject_test
from .inject_update_page import inject_update_page

assert inject_list_page
assert inject_detail_page
assert inject_insert_page
assert inject_update_page
assert inject_delete_page
assert inject_repo
assert inject_schema
assert inject_test
