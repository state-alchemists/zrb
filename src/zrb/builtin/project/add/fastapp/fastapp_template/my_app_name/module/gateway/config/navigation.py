from my_app_name.module.gateway.schema.navigation import Navigation, Page, PageGroup

APP_NAVIGATION = Navigation()

APP_NAVIGATION.append_page(Page(name="gateway.home", caption="Home", url="/"))

auth_menu = APP_NAVIGATION.append_page_group(
    PageGroup(
        name="auth",
        caption="Authorization",
    )
)

auth_menu.append_page(
    Page(
        name="auth.permission",
        caption="Permission",
        url="/auth/permissions",
        permission="permission:read",
    )
)

auth_menu.append_page(
    Page(
        name="auth.role",
        caption="Role",
        url="/auth/roles",
        permission="role:read",
    )
)

auth_menu.append_page(
    Page(
        name="auth.user",
        caption="User",
        url="/auth/users",
        permission="user:read",
    )
)
