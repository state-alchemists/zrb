# Web Auth Example

Shows how to configure authentication for Zrb's web UI.

## Quick Setup

```python
from zrb import User
from zrb.config.web_auth_config import web_auth_config

# Enable authentication
web_auth_config.enable_auth = True

# Add users
web_auth_config.append_user(
    User(
        username="admin",
        password="secret",
        accessible_tasks=["*"],  # All tasks
    )
)

# Set guest-accessible tasks
web_auth_config.guest_accessible_tasks = ["public-task"]
```

## Running

```bash
cd examples/web-auth

# Start web UI
zrb serve --port 8000

# Access http://localhost:8000
```

## User Configuration

### Full Access User

```python
User(
    username="admin",
    password="admin123",
    accessible_tasks=["*"],  # All tasks
)
```

### Limited Access User

```python
User(
    username="jack",
    password="jack123",
    accessible_tasks=["hello", "greet"],  # Only these
)
```

### Guest Access

```python
# Tasks visible to unauthenticated users
web_auth_config.guest_accessible_tasks = ["hello"]
```

## Access Matrix

| User | Tasks |
|------|-------|
| Guest | `hello` |
| `jack` | `hello`, `greet` |
| `admin` | ALL (`*`) |

## Authentication Flow

```mermaid
flowchart TB
    Browser -->|Request| WebUI["Web UI"]
    WebUI --> Login["Login Page<br />(if needed)"]
    Login --> Check["Check ACL<br />for Task"]
    Check --> Run["Run Task<br />(if OK)"]
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| `enable_auth` | Turn on authentication |
| `append_user()` | Add a user |
| `accessible_tasks` | Tasks user can run |
| `*` | Wildcard for all tasks |
| `guest_accessible_tasks` | Public tasks |

## Security Notes

1. **Use strong passwords** in production
2. **Limit guest access** to non-sensitive tasks
3. **Use environment variables** for credentials:

```python
import os

web_auth_config.append_user(
    User(
        username="admin",
        password=os.environ.get("ADMIN_PASSWORD", "change-me"),
        accessible_tasks=["*"],
    )
)
```

4. **HTTPS** is recommended for production
