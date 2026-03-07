🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Web UI

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

By default, the server will be accessible at `http://localhost:21213`.

### Customizing the Port

You can change the default port using the `ZRB_WEB_HTTP_PORT` environment variable.

```bash
export ZRB_WEB_HTTP_PORT=8000
zrb server start
```

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

Zrb's Web UI includes an experimental authentication system. By default, it's disabled for ease of use in local development.

### Enabling Authentication

```bash
export ZRB_WEB_ENABLE_AUTH=1
zrb server start
```

### Default Users

| User Type | Username | Password | Access |
|-----------|----------|----------|--------|
| Guest | `user` (configurable) | Prompted | Limited tasks |
| Super Admin | `admin` (configurable) | `admin` (change me!) | Full access |

> ⚠️ **Warning:** Change the default admin password before deploying to production!

### Programmatic User Management

You can define custom users and their accessible tasks directly in your `zrb_init.py`:

```python
from zrb import web_auth_config, User

web_auth_config.enable_auth = True 

web_auth_config.append_user(
    User(
        username="ace",
        password="ultramanNumber5",
        accessible_tasks=["encode-base64", "throw-dice"]
    )
)

web_auth_config.guest_accessible_tasks = ["throw-dice"]
```

### Authentication Environment Variables

| Variable | Description |
|----------|-------------|
| `ZRB_WEB_SECRET_KEY` | Token generation key (**crucial for production**) |
| `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token validity |
| `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token validity |

---

## 4. Customizing Web UI Appearance

You can customize the visual styling of the Web UI using environment variables.

| Variable | Description |
|----------|-------------|
| `ZRB_WEB_TITLE` | Browser tab title |
| `ZRB_WEB_JARGON` | Tagline on homepage |
| `ZRB_WEB_HOMEPAGE_INTRO` | Introductory text |
| `ZRB_WEB_FAVICON_PATH` | Path to custom favicon |
| `ZRB_WEB_CSS_PATH` | Colon-separated custom CSS paths |
| `ZRB_WEB_JS_PATH` | Colon-separated custom JS paths |
| `ZRB_WEB_COLOR` | Pico CSS theme color (`amber`, `red`, `blue`, etc.) |

> 💡 **Tip:** See [Pico CSS docs](https://picocss.com/docs/version-picker) for available theme colors.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `zrb server start` | Start web server |
| `zrb server start --port 8000` | Start on custom port |

| Variable | Default | Description |
|----------|---------|-------------|
| `ZRB_WEB_HTTP_PORT` | `21213` | Server port |
| `ZRB_WEB_ENABLE_AUTH` | `0` | Enable authentication |
| `ZRB_WEB_COLOR` | `amber` | Theme color |

---