# MyEntity related methods


@abstractmethod
async def get_my_entity_by_id(self, my_entity_id: str) -> MyEntityResponse:
    """Get my entity by id"""


@abstractmethod
async def get_my_entities(
    self,
    page: int = 1,
    page_size: int = 10,
    sort: str | None = None,
    filter: str | None = None,
) -> MultipleMyEntityResponse:
    """Get my entities by filter and sort"""


@abstractmethod
async def create_my_entity_bulk(
    self, data: list[MyEntityCreateWithAudit]
) -> list[MyEntityResponse]:
    """Create new my entities"""


@abstractmethod
async def create_my_entity(self, data: MyEntityCreateWithAudit) -> MyEntityResponse:
    """Create a new my entities"""


@abstractmethod
async def update_my_entity_bulk(
    self, my_entity_ids: list[str], data: MyEntityUpdateWithAudit
) -> MyEntityResponse:
    """Update some my entities"""


@abstractmethod
async def update_my_entity(
    self, my_entity_id: str, data: MyEntityUpdateWithAudit
) -> MyEntityResponse:
    """Update a my entity"""


@abstractmethod
async def delete_my_entity_bulk(
    self, my_entity_ids: str, deleted_by: str
) -> MyEntityResponse:
    """Delete some my entities"""


@abstractmethod
async def delete_my_entity(
    self, my_entity_id: str, deleted_by: str
) -> MyEntityResponse:
    """Delete a my entity"""
