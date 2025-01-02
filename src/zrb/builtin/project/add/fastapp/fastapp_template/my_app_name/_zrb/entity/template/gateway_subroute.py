# MyEntity routes


@app.get("/api/v1/my-entities", response_model=MultipleMyEntityResponse)
async def get_my_entities(
    page: int = 1,
    page_size: int = 10,
    sort: str | None = None,
    filter: str | None = None,
) -> MultipleMyEntityResponse:
    return await my_module_client.get_my_entities(
        page=page, page_size=page_size, sort=sort, filter=filter
    )


@app.get("/api/v1/my-entities/{my_entity_id}", response_model=MyEntityResponse)
async def get_my_entity_by_id(my_entity_id: str) -> MyEntityResponse:
    return await my_module_client.get_my_entity_by_id(my_entity_id)


@app.post(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def create_my_entity_bulk(data: list[MyEntityCreate]):
    return await my_module_client.create_my_entity_bulk(
        [row.with_audit(created_by="system") for row in data]
    )


@app.post(
    "/api/v1/my-entities",
    response_model=MyEntityResponse,
)
async def create_my_entity(data: MyEntityCreate):
    return await my_module_client.create_my_entity(data.with_audit(created_by="system"))


@app.put(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def update_my_entity_bulk(my_entity_ids: list[str], data: MyEntityUpdate):
    return await my_module_client.update_my_entity_bulk(
        my_entity_ids, data.with_audit(updated_by="system")
    )


@app.put(
    "/api/v1/my-entities/{my_entity_id}",
    response_model=MyEntityResponse,
)
async def update_my_entity(my_entity_id: str, data: MyEntityUpdate):
    return await my_module_client.update_my_entity(data.with_audit(updated_by="system"))


@app.delete(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def delete_my_entity_bulk(my_entity_ids: list[str]):
    return await my_module_client.delete_my_entity_bulk(
        my_entity_ids, deleted_by="system"
    )


@app.delete(
    "/api/v1/my-entities/{my_entity_id}",
    response_model=MyEntityResponse,
)
async def delete_my_entity(my_entity_id: str):
    return await my_module_client.delete_my_entity(my_entity_id, deleted_by="system")
