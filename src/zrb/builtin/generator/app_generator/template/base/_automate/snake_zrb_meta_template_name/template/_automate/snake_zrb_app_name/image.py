from zrb import Env, StrInput

###############################################################################
# Input Definitions
###############################################################################

image_input = StrInput(
    name='kebab-zrb-app-name-image',
    description='Image name of "kebab-zrb-app-name"',
    prompt='Image name of "kebab-zrb-app-name"',
    default='zrb-app-image-name:latest'
)


###############################################################################
# Env Definitions
###############################################################################

image_env = Env(
    name='IMAGE',
    os_name='CONTAINER_ZRB_ENV_PREFIX_IMAGE',
    default='{{input.snake_zrb_app_name_image}}'
)
