🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# Web Authentication Configuration

## Overview

The `WebAuthConfig` class provides configuration settings for web authentication. It includes parameters for token management, user roles, and authentication behavior.

Zrb has a `web_auth_config` singleton that you can access and manipulate by importing `zrb.web_auth_config` in your `zrb_init.py`

```python
from zrb import web_auth_config, User

# Enable authentication:
web_auth_config.set_enable_auth(True) 

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
web_auth_config.set_guest_accessible_tasks(["throw-dice", "shuffle"])
```

## Properties

### `secret_key`
- **Description**: The secret key for token generation.
- **Type**: `str`

### `access_token_expire_minutes`
- **Description**: The expiration time for access tokens in minutes.
- **Type**: `int`

### `refresh_token_expire_minutes`
- **Description**: The expiration time for refresh tokens in minutes.
- **Type**: `int`

### `access_token_cookie_name`
- **Description**: The name of the access token cookie.
- **Type**: `str`

### `refresh_token_cookie_name`
- **Description**: The name of the refresh token cookie.
- **Type**: `str`

### `enable_auth`
- **Description**: Whether authentication is enabled.
- **Type**: `bool`

### `super_admin_username`
- **Description**: The username of the super admin.
- **Type**: `str`

### `super_admin_password`
- **Description**: The password of the super admin.
- **Type**: `str`

### `guest_username`
- **Description**: The username for guest users.
- **Type**: `str`

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

### `set_secret_key(secret_key: str)`
- **Description**: Sets the secret key.

### `set_access_token_expire_minutes(minutes: int)`
- **Description**: Sets the access token expiration time.

### `set_refresh_token_expire_minutes(minutes: int)`
- **Description**: Sets the refresh token expiration time.

### `set_access_token_cookie_name(name: str)`
- **Description**: Sets the access token cookie name.

### `set_refresh_token_cookie_name(name: str)`
- **Description**: Sets the refresh token cookie name.

### `set_enable_auth(enable: bool)`
- **Description**: Enables or disables authentication.

### `set_super_admin_username(username: str)`
- **Description**: Sets the super admin username.

### `set_super_admin_password(password: str)`
- **Description**: Sets the super admin password.

### `set_guest_username(username: str)`
- **Description**: Sets the guest username.

### `set_guest_accessible_tasks(tasks: list[AnyTask | str])`
- **Description**: Sets the list of tasks accessible to guests.

### `set_find_user_by_username(find_user_by_username: Callable[[str], User | None])`
- **Description**: Sets the function to find a user by username.

### `append_user(user: User)`
- **Description**: Adds a user to the user list.

### `find_user_by_username(username: str) -> User | None`
- **Description**: Finds a user by username.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)
