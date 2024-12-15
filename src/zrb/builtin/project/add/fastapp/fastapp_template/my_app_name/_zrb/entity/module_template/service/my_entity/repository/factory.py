from my_app_name.common.db_engine import engine
from my_app_name.config import APP_REPOSITORY_TYPE
from my_app_name.module.my_module.service.my_entity.repository.my_entity_db_repository import (
    MyEntityDBRepository,
)
from my_app_name.module.my_module.service.my_entity.repository.my_entity_repository import (
    MyEntityRepository,
)

if APP_REPOSITORY_TYPE == "db":
    my_entity_repository: MyEntityRepository = MyEntityDBRepository(engine)
else:
    my_entity_repository: MyEntityRepository = None
