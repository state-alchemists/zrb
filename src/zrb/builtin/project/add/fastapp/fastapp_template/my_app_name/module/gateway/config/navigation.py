from my_app_name.module.gateway.schema.navigation import Menu, Navigation, Submenu

APP_NAVIGATION = Navigation()

auth_menu = APP_NAVIGATION.add_menu(
    Menu(
        name="auth",
        caption="Authorization",
    )
)

auth_menu.add_submenu(
    Submenu(
        name="auth.permission",
        caption="Permission",
        permission="permission:read",
    )
)
auth_menu.add_submenu(
    Submenu(
        name="auth.role",
        caption="Role",
        permission="role:read",
    )
)
auth_menu.add_submenu(
    Submenu(
        name="auth.user",
        caption="User",
        permission="user:read",
    )
)
