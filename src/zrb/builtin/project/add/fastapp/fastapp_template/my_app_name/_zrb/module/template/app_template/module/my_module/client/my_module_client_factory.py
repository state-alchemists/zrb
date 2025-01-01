from my_app_name.config import APP_COMMUNICATION
from my_app_name.module.my_module.client.my_module_api_client import MyModuleAPIClient
from my_app_name.module.my_module.client.my_module_client import MyModuleClient
from my_app_name.module.my_module.client.my_module_direct_client import (
    MyModuleDirectClient,
)

if APP_COMMUNICATION == "direct":
    my_module_client: MyModuleClient = MyModuleDirectClient()
elif APP_COMMUNICATION == "api":
    my_module_client: MyModuleClient = MyModuleAPIClient()
