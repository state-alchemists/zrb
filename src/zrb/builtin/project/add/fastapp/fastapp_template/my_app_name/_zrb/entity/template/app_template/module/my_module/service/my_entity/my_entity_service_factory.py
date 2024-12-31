from my_app_name.common.logger_factory import logger
from my_app_name.module.my_module.service.my_entity.my_entity_service import (
    MyEntityService,
)
from my_app_name.module.my_module.service.my_entity.repository.my_entity_repository_factory import (
    my_entity_repository,
)

my_entity_service = MyEntityService(logger, my_entity_repository=my_entity_repository)
