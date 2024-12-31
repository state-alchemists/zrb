from my_app_name.common.logger_factory import logger
from my_app_name.module.auth.service.role.repository.role_repository_factory import (
    role_repository,
)
from my_app_name.module.auth.service.role.role_service import RoleService

role_service = RoleService(logger, role_repository=role_repository)
