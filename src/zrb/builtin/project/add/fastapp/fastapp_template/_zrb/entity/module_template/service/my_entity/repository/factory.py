from fastapp_template.common.db_engine import engine
from fastapp_template.config import APP_REPOSITORY_TYPE
from fastapp_template.module.my_module.service.my_entity.repository.my_entity_db_repository import (
    MyEntityDBRepository,
)
from fastapp_template.module.my_module.service.my_entity.repository.my_entity_repository import (
    MyEntityRepository,
)

if APP_REPOSITORY_TYPE == "db":
    my_entity_repository: MyEntityRepository = MyEntityDBRepository(engine)
else:
    my_entity_repository: MyEntityRepository = None
