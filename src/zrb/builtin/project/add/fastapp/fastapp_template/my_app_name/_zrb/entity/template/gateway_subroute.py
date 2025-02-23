# MyEntity routes


@app.get("/my-module/my-entities", include_in_schema=False)
def my_entities_crud_ui(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 10,
    sort: str | None = None,
    filter: str | None = None,
):
    if not current_user.has_permission("my-entity:read"):
        return render_error(error_message="Access denied", status_code=403)
    return render_content(
        view_path=os.path.join("my-module", "my-entity.html"),
        current_user=current_user,
        page_name="my-module.my-entity",
        page=page,
        page_size=page_size,
        sort=sort,
        filter=filter,
        allow_create=current_user.has_permission("my-entity:create"),
        allow_update=current_user.has_permission("my-entity:update"),
        allow_delete=current_user.has_permission("my-entity:delete"),
    )


@app.get("/api/v1/my-entities", response_model=MultipleMyEntityResponse)
async def get_my_entities(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 10,
    sort: str | None = None,
    filter: str | None = None,
) -> MultipleMyEntityResponse:
    if not current_user.has_permission("my-entity:read"):
        raise ForbiddenError("Access denied")
    return await my_module_client.get_my_entities(
        page=page, page_size=page_size, sort=sort, filter=filter
    )


@app.get("/api/v1/my-entities/{my_entity_id}", response_model=MyEntityResponse)
async def get_my_entity_by_id(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    my_entity_id: str,
) -> MyEntityResponse:
    if not current_user.has_permission("my-entity:read"):
        raise ForbiddenError("Access denied")
    return await my_module_client.get_my_entity_by_id(my_entity_id)


@app.post(
    "/api/v1/my-entities/bulk",
    response_model=list[MyEntityResponse],
)
async def create_my_entity_bulk(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    data: list[MyEntityCreate],
) -> list[MyEntityResponse]:
    if not current_user.has_permission("my-entity:create"):
        raise ForbiddenError("Access denied")
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
    if not current_user.has_permission("my-entity:create"):
        raise ForbiddenError("Access denied")
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
    if not current_user.has_permission("my-entity:update"):
        raise ForbiddenError("Access denied")
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
    if not current_user.has_permission("my-entity:update"):
        raise ForbiddenError("Access denied")
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
    if not current_user.has_permission("my-entity:delete"):
        raise ForbiddenError("Access denied")
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
    if not current_user.has_permission("my-entity:delete"):
        raise ForbiddenError("Access denied")
    return await my_module_client.delete_my_entity(
        my_entity_id, deleted_by=current_user.id
    )
