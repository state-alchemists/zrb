from zrb import Env

image_env = Env(
    name="IMAGE",
    os_name="CONTAINER_ZRB_ENV_PREFIX_IMAGE",
    default="{{input.snake_zrb_app_name_image}}",
)
