import os

from zrb import EnvFile, ServiceConfig

from .._constant import APP_DIR

snake_zrb_app_name_service_config = ServiceConfig(
    env_files=[
        EnvFile(
            path=os.path.join(APP_DIR, "template.env"),
            prefix="CONTAINER_ZRB_ENV_PREFIX",
        )
    ]
)
