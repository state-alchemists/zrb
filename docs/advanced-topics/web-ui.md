🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Web UI

# Web UI (Graphical Interface)

Zrb isn't just a command-line tool; it also provides an experimental, sleek web-based User Interface. This allows you to explore, trigger, and monitor your automation tasks from any web browser, offering a more visual experience.

---

## 1. Starting the Web Server

To launch the Zrb Web UI, simply run the `server start` command:

```bash
zrb server start
```

By default, the server will be accessible at `http://localhost:21213`.

### Customizing the Port
You can change the default port using the `ZRB_WEB_HTTP_PORT` environment variable (see [Environment Variables & Overrides](../configuration/env-vars.md)).

```bash
export ZRB_WEB_HTTP_PORT=8000
zrb server start
```

---

## 2. Exploring the Web UI

Once the server is running, open your web browser and navigate to the specified address (e.g., `http://localhost:21213`). You will see a clean interface listing all your defined Zrb tasks and groups.

**Key Features:**
-   **Task Browsing:** Navigate through your task hierarchy.
-   **Input Forms:** Tasks with defined inputs will automatically generate web forms for easy parameter input.
-   **Execution:** Trigger tasks directly from the browser.
-   **Monitoring:** View task execution status and logs.

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

---

## 3. Web Authentication (Experimental)

Zrb's Web UI includes an experimental authentication system. By default, it's disabled for ease of use in local development.

### Enabling Authentication
To secure your Web UI, set the `ZRB_WEB_ENABLE_AUTH` environment variable to `1`:

```bash
export ZRB_WEB_ENABLE_AUTH=1
zrb server start
```

Once enabled, you will be prompted for a username and password.

### Default Users
-   **Guest User:**
    -   Username: `user` (configurable via `ZRB_WEB_GUEST_USERNAME`)
    -   Password: (no default, you'll be prompted)
    -   Access: Limited to tasks explicitly allowed (e.g., `web_auth_config.guest_accessible_tasks`).
-   **Super Admin:**
    -   Username: `admin` (configurable via `ZRB_WEB_SUPER_ADMIN_USERNAME`)
    -   Password: `admin` (configurable via `ZRB_WEB_SUPER_ADMIN_PASSWORD`)
    -   Access: Full access to all tasks.

### Programmatic User Management
You can define custom users and their accessible tasks directly in your `zrb_init.py` using the `web_auth_config` singleton.

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

### Other Authentication Settings
-   `ZRB_WEB_SECRET_KEY`: Used for token generation. **Crucial for security in production.**
-   `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`: How long access tokens are valid.
-   `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES`: How long refresh tokens are valid.
-   `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME` / `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME`: Cookie names.

(See [Environment Variables & Overrides](../configuration/env-vars.md) for full details on these variables).

---

## 4. Customizing Web UI Appearance

You can customize the visual styling of the Web UI using environment variables.

-   `ZRB_WEB_TITLE`: The title displayed in the browser tab.
-   `ZRB_WEB_JARGON`: A tagline displayed on the homepage.
-   `ZRB_WEB_HOMEPAGE_INTRO`: Introductory text for the homepage.
-   `ZRB_WEB_FAVICON_PATH`: Path to a custom favicon (`.ico` or `.png`).
-   `ZRB_WEB_CSS_PATH`: Colon-separated list of paths to custom CSS files.
-   `ZRB_WEB_JS_PATH`: Colon-separated list of paths to custom JavaScript files.
-   `ZRB_WEB_COLOR`: A Pico CSS theme color (e.g., `amber`, `red`, `blue`). See [Pico CSS docs](https://picocss.com/docs/version-picker) for options.

(See [Environment Variables & Overrides](../configuration/env-vars.md) for full details on these variables).
