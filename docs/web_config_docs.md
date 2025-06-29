# Web Authentication Configuration Documentation

## Overview
The `WebAuthConfig` class provides configuration settings for web authentication. It includes parameters for token management, user roles, and authentication behavior.

## Properties

### `port`
- **Description**: The port number for the web server.
- **Type**: `int`

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

### `set_port(port: int)`
- **Description**: Sets the port number.

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

## Example Usage
```python
from zrb.runner.web_auth_config import web_auth_config

# Set a custom port
web_auth_config.set_port(8080)

# Get the default secret key
print(web_auth_config.secret_key)
```