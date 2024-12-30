@app.get("/api/v1/my_entities", response_model=MultipleMyEntityResponse)
async def get_all_my_entities(
    page: int = 1,
    page_size: int = 10,
    sort: str | None = None,
    filter: str | None = None,
) -> MultipleMyEntityResponse:
    return await my_module_client.get_all_my_entities(
        page=page, page_size=page_size, sort=sort, filter=filter
    )


@app.get("/api/v1/my_entities/{my_entity_id}", response_model=MyEntityResponse)
async def get_my_entity_by_id(my_entity_id: str) -> MyEntityResponse:
    return await my_module_client.get_my_entity_by_id(my_entity_id)


@app.post(
    "/api/v1/my_entities", response_model=MyEntityResponse | list[MyEntityResponse]
)
async def create_my_entity(data: MyEntityCreate | list[MyEntityCreate]):
    if isinstance(data, MyEntityCreate):
        data_dict = data.model_dump(exclude_unset=True)
        audited_data = MyEntityCreateWithAudit(**data_dict, created_by="system")
        return await my_module_client.create_my_entity(audited_data)
    audited_data = [
        MyEntityCreateWithAudit(
            **row.model_dump(exclude_unset=True), created_by="system"
        )
        for row in data
    ]
    return await my_module_client.create_my_entity(audited_data)


@app.put("/api/v1/my_entities/{my_entity_id}", response_model=MyEntityResponse)
async def update_my_entity(my_entity_id: str, data: MyEntityUpdate) -> MyEntityResponse:
    data_dict = data.model_dump(exclude_unset=True)
    audited_data = MyEntityUpdateWithAudit(**data_dict, updated_by="system")
    return await my_module_client.update_my_entity(my_entity_id, audited_data)


@app.delete("/api/v1/my_entities/{my_entity_id}", response_model=MyEntityResponse)
async def delete_my_entity(my_entity_id: str) -> MyEntityResponse:
    return await my_module_client.delete_my_entity(my_entity_id, deleted_by="system")
