🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# Web Authentication Configuration

## Overview

The `WebAuthConfig` class in [`src/zrb/runner/web_auth_config.py`](../../../src/zrb/runner/web_auth_config.py) provides configuration settings for web authentication. It includes parameters for authentication token management, user roles, and authentication behavior.

Zrb has a `web_auth_config` singleton that you can access and manipulate by importing `zrb.web_auth_config` in your `zrb_init.py`

```python
from zrb import web_auth_config, User

# Enable authentication:
web_auth_config.enable_auth = True 

# Add a user named Ace, and Taro, define their password and accessible tasks.
# The accessible tasks can be:
# - Instance of AnyTask
# - A string representing the task name
web_auth_config.append_user(
    User(
        username="ace",
        password="ultramanNumber5",
        accessible_tasks=[
            "encode-base64",
            "decode-base64",
            "validate-base64",
            "throw-dice",
            "shuffle",
        ]
    ),
    User(
        username="taro",
        password="ultramanNumber6",
        accessible_tasks=[
            "generate-curl",
            "encode-jwt",
            "decode-jwt",
            "hash-md5",
            "validate-md5",
            "throw-dice",
            "shuffle",
        ]
    )
)

# Define accessible tasks for guest users
web_auth_config.guest_accessible_tasks = ["throw-dice", "shuffle"]
```

## Properties

### `secret_key`
- **Description**: The secret key for token generation.
- **Type**: `str`
- **Environment Variable**: `ZRB_WEB_SECRET`

### `access_token_expire_minutes`
- **Description**: The expiration time for access tokens in minutes.
- **Type**: `int`
- **Environment Variable**: `ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES`

### `refresh_token_expire_minutes`
- **Description**: The expiration time for refresh tokens in minutes.
- **Type**: `int`
- **Environment Variable**: `ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES`

### `access_token_cookie_name`
- **Description**: The name of the access token cookie.
- **Type**: `str`
- **Environment Variable**: `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME`

### `refresh_token_cookie_name`
- **Description**: The name of the refresh token cookie.
- **Type**: `str`
- **Environment Variable**: `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME`

### `enable_auth`
- **Description**: Whether authentication is enabled.
- **Type**: `bool`
- **Environment Variable**: `ZRB_WEB_ENABLE_AUTH`

### `super_admin_username`
- **Description**: The username of the super admin.
- **Type**: `str`
- **Environment Variable**: `ZRB_WEB_SUPER_ADMIN_USERNAME`

### `super_admin_password`
- **Description**: The password of the super admin.
- **Type**: `str`
- **Environment Variable**: `ZRB_WEB_SUPER_ADMIN_PASSWORD`

### `guest_username`
- **Description**: The username for guest users.
- **Type**: `str`
- **Environment Variable**: `ZRB_WEB_GUEST_USERNAME`

### `guest_accessible_tasks`
- **Description**: List of tasks accessible to guest users.
- **Type**: `list[AnyTask | str]`

### `default_user`
- **Description**: The default user instance.
- **Type**: `User`

### `super_admin`
- **Description**: The super admin user instance.
- **Type**: `User`

### `user_list`
- **Description**: The list of users.
- **Type**: `list[User]`

## Methods

### `append_user(user: User)`
- **Description**: Adds a user to the user list.

### `find_user_by_username(username: str) -> User | None`
- **Description**: Finds a user by username.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)
