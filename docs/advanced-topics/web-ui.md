🔖 [Documentation Home](../README.md) > [Advanced Topics](./) > Web UI

# Web UI (Graphical Interface)

Zrb isn't just a command-line tool; it also provides an experimental, sleek web-based User Interface. This allows you to explore, trigger, and monitor your automation tasks from any web browser, offering a more visual experience.

---

## Table of Contents

- [Starting the Web Server](#1-starting-the-web-server)
- [Exploring the Web UI](#2-exploring-the-web-ui)
- [Web Authentication](#3-web-authentication-experimental)
- [Customizing Appearance](#4-customizing-web-ui-appearance)
- [Quick Reference](#quick-reference)

---

## 1. Starting the Web Server

To launch the Zrb Web UI, run the `server start` command:

```bash
zrb server start
```

By default, the server binds to `127.0.0.1` and is only reachable from the local machine at `http://localhost:21213`.

### Customizing the Port

You can change the default port using the `ZRB_WEB_HTTP_PORT` environment variable.

```bash
export ZRB_WEB_HTTP_PORT=8000
zrb server start
```

### Customizing the Host

To make the server reachable from other machines (e.g. a LAN or container network), set `ZRB_WEB_HTTP_HOST` explicitly:

```bash
export ZRB_WEB_HTTP_HOST=0.0.0.0
zrb server start
```

> ⚠️ **The server refuses to start on a non-loopback host unless it is actually secured.** Binding beyond loopback exposes task execution — arbitrary command execution — to anyone who can reach this host, so `zrb server start` exits non-zero unless *all* of the following hold:
>
> | Requirement | Why |
> |---|---|
> | `ZRB_WEB_AUTH_ENABLED=1` | Otherwise there is no login at all |
> | `ZRB_WEB_SUPER_ADMIN_PASSWORD` is non-empty, not the default, ≥ 12 characters | It is the only thing standing between the internet and your shell |
> | `ZRB_WEB_SECRET_KEY` is non-empty, not the default, ≥ 32 characters | It signs the session JWTs; a short key is forgeable |
>
> With auth enabled, every failing credential is listed at once. "Not the default" is not sufficient on its own — an explicitly empty or one-character value is rejected too. Any loopback address is exempt (`127.0.0.1`, `127.0.0.2`, `::1`, its expanded `0:0:0:0:0:0:0:1` form, and `localhost`); a hostname that cannot be proven loopback-only is treated as exposed. There is no override flag — the alternative to meeting these requirements is to keep the loopback bind and put your own proxy in front.

---

## 2. Exploring the Web UI

Once the server is running, open your web browser and navigate to the specified address (e.g., `http://localhost:21213`). You will see a clean interface listing all your defined Zrb tasks and groups.

**Key Features:**

| Feature | Description |
|---------|-------------|
| Task Browsing | Navigate through your task hierarchy |
| Input Forms | Auto-generated web forms for task inputs |
| Execution | Trigger tasks directly from browser |
| Monitoring | View task status and logs |

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

---

## 3. Web Authentication (Experimental)

Zrb's Web UI includes an experimental authentication system. By default, it's disabled for ease of use in local development — safe by default because the server also only binds to `127.0.0.1` unless you explicitly set `ZRB_WEB_HTTP_HOST`.

### Enabling Authentication

```bash
export ZRB_WEB_AUTH_ENABLED=1
zrb server start
```

### Default Users

| User Type | Username | Password | Access |
|-----------|----------|----------|--------|
| Guest | `user` (`ZRB_WEB_GUEST_USERNAME`) | None — anyone not logged in | Only `guest_accessible_tasks` |
| Super Admin | `admin` (`ZRB_WEB_SUPER_ADMIN_USERNAME`) | `admin` (`ZRB_WEB_SUPER_ADMIN_PASSWORD` — change me!) | Full access |

> ⚠️ **Warning:** Change the default admin password before deploying to production!

### Programmatic User Management

You can define custom users and their accessible tasks directly in your `zrb_init.py`:

```python
from zrb import web_auth_config, User

web_auth_config.enable_auth = True 

web_auth_config.add_user(
    User(
        username="ace",
        password="ultramanNumber5",
        accessible_tasks=["encode-base64", "throw-dice"]
    )
)

web_auth_config.guest_accessible_tasks = ["throw-dice"]
```

A `User` has `username`, `password`, `accessible_tasks` (task objects or names), and two flags: `is_super_admin` (access to every task) and `is_guest` (marks the not-logged-in user). `add_user` raises `ValueError` for a username already taken.

### Looking Users Up Elsewhere

To check users against your own store (a database, LDAP) instead of registering them up front, set `find_user_by_username_callback`. It receives a username and returns a `User` or `None`. Zrb asks it first and falls back to the registered users when it returns `None`.

A plain `User` compares its `password` with the typed one as plain text, so never return a stored password that way. Return a `User` subclass whose `is_password_match` verifies your stored hash instead — login calls that method:

```python
import hashlib
import hmac

from zrb import User, web_auth_config


class HashedUser(User):
    salt: bytes = b""

    def is_password_match(self, password: str) -> bool:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), self.salt, 600_000)
        return hmac.compare_digest(self.password, digest.hex())


def find_user(username: str) -> User | None:
    row = my_db.get_user(username)  # your own lookup
    if row is None:
        return None
    return HashedUser(
        username=row.name,
        password=row.password_hash,  # hex PBKDF2 digest, never the password
        salt=row.salt,
        accessible_tasks=row.tasks,
    )


web_auth_config.find_user_by_username_callback = find_user
```

### Settings in Code

Every authentication setting is also a read/write property on `web_auth_config`, which wins over the matching environment variable: `enable_auth`, `secret_key`, `secure_cookies`, `access_token_expire_minutes`, `refresh_token_expire_minutes`, `access_token_cookie_name`, `refresh_token_cookie_name`, `super_admin_username`, `super_admin_password`, `guest_username`, and `guest_accessible_tasks`. The startup check that refuses an insecure non-loopback bind reads these effective values.

### Authentication Environment Variables

| Variable | Description |
|----------|-------------|
| `ZRB_WEB_SECRET_KEY` | Token generation key (**crucial for production**) |
| `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token validity |
| `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token validity |

> 🔒 **Cookie security.** Auth cookies are issued with `HttpOnly`, `Secure`, and `SameSite=Lax`. The `Secure` flag means browsers only send them over HTTPS (modern browsers treat `http://localhost` as a secure context, so local development is unaffected) — terminate TLS in front of Zrb for any non-localhost deployment. The `Secure` flag is on by default; if you must serve over plain HTTP on a non-localhost host, set `ZRB_WEB_AUTH_SECURE_COOKIES=off` (otherwise browsers silently drop the cookies and login appears to fail). Only access tokens authenticate a request; a refresh token can only be exchanged at the refresh endpoint, never used directly as an access token.

---

## 4. Customizing Web UI Appearance

You can customize the visual styling of the Web UI using environment variables.

| Variable | Description |
|----------|-------------|
| `ZRB_WEB_TITLE` | Browser tab title |
| `ZRB_WEB_JARGON` | Tagline on homepage |
| `ZRB_WEB_HOMEPAGE_INTRO` | Introductory text |
| `ZRB_WEB_FAVICON_PATH` | Path to custom favicon |
| `ZRB_WEB_CSS_PATH` | Colon-separated (semicolon on Windows) custom CSS paths |
| `ZRB_WEB_JS_PATH` | Colon-separated (semicolon on Windows) custom JS paths |
| `ZRB_WEB_COLOR` | Pico CSS theme color (`amber`, `red`, `blue`, etc.) |

> 💡 **Tip:** See [Pico CSS docs](https://picocss.com/docs/version-picker) for available theme colors.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `zrb server start` | Start web server |
| `ZRB_WEB_HTTP_PORT=8000 zrb server start` | Start on custom port |

| Variable | Default | Description |
|----------|---------|-------------|
| `ZRB_WEB_HTTP_HOST` | `127.0.0.1` | Server bind host; non-loopback exposes the server to the network |
| `ZRB_WEB_HTTP_PORT` | `21213` | Server port |
| `ZRB_WEB_AUTH_ENABLED` | `off` | Enable authentication |
| `ZRB_WEB_COLOR` | `` (empty) | Theme color |

---

🔖 [Documentation Home](../README.md) > [Advanced Topics](./) > Web UI
