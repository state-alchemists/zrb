# MyEntity routes


@app.get("/api/v1/my-entities", response_model=MultipleMyEntityResponse)
async def get_my_entities(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 10,
    sort: str | None = None,
    filter: str | None = None,
) -> MultipleMyEntityResponse:
    return await my_module_client.get_my_entities(
        page=page, page_size=page_size, sort=sort, filter=filter
    )


@app.get("/api/v1/my-entities/{my_entity_id}", response_model=MyEntityResponse)
async def get_my_entity_by_id(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    my_entity_id: str,
) -> MyEntityResponse:
    return await my_module_client.get_my_entity_by_id(my_entity_id)


@app.post(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def create_my_entity_bulk(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    data: list[MyEntityCreate],
) -> list[MyEntityResponse]:
    return await my_module_client.create_my_entity_bulk(
        [row.with_audit(created_by=current_user.id) for row in data]
    )


@app.post(
    "/api/v1/my-entities",
    response_model=MyEntityResponse,
)
async def create_my_entity(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    data: MyEntityCreate,
) -> MyEntityResponse:
    return await my_module_client.create_my_entity(
        data.with_audit(created_by=current_user.id)
    )


@app.put(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def update_my_entity_bulk(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    my_entity_ids: list[str],
    data: MyEntityUpdate,
) -> list[MyEntityResponse]:
    return await my_module_client.update_my_entity_bulk(
        my_entity_ids, data.with_audit(updated_by=current_user.id)
    )


@app.put(
    "/api/v1/my-entities/{my_entity_id}",
    response_model=MyEntityResponse,
)
async def update_my_entity(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    my_entity_id: str,
    data: MyEntityUpdate,
) -> MyEntityResponse:
    return await my_module_client.update_my_entity(
        my_entity_id, data.with_audit(updated_by=current_user.id)
    )


@app.delete(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def delete_my_entity_bulk(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    my_entity_ids: list[str],
) -> list[MyEntityResponse]:
    return await my_module_client.delete_my_entity_bulk(
        my_entity_ids, deleted_by=current_user.id
    )


@app.delete(
    "/api/v1/my-entities/{my_entity_id}",
    response_model=MyEntityResponse,
)
async def delete_my_entity(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    my_entity_id: str,
) -> MyEntityResponse:
    return await my_module_client.delete_my_entity(
        my_entity_id, deleted_by=current_user.id
    )
