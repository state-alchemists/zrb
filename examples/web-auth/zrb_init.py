"""
Web Auth Example

Shows how to configure web authentication for Zrb's web UI.
"""

from zrb import Task, User, cli
from zrb.config.web_auth_config import web_auth_config

# =============================================================================
# Enable Authentication
# =============================================================================

# Enable authentication for the web UI
web_auth_config.enable_auth = True

# =============================================================================
# Add Users
# =============================================================================

# Add a user with access to specific tasks
web_auth_config.append_user(
    User(
        username="jack",
        password="jack123",
        accessible_tasks=["hello", "greet"],  # Can only run these tasks
    )
)

web_auth_config.append_user(
    User(
        username="admin",
        password="admin123",
        accessible_tasks=["*"],  # Can run ALL tasks
    )
)

# =============================================================================
# Guest Access
# =============================================================================

# Tasks that guests (unauthenticated users) can access
web_auth_config.guest_accessible_tasks = ["hello"]  # Only "hello" is public

# =============================================================================
# Example Tasks
# =============================================================================


@Task(name="hello", action=lambda ctx: "Hello, World!")
def hello(ctx):
    return "Hello, World!"


cli.add_task(hello)


@Task(name="greet", input=[{"name": "name", "default": "Friend"}])
def greet(ctx):
    return f"Greetings, {ctx.input.name}!"


cli.add_task(greet)


# Admin-only task
@Task(name="admin-only")
def admin_task(ctx):
    ctx.print("This is an admin-only task")
    return "Admin action completed"


cli.add_task(admin_task)

# =============================================================================
# Running Web UI
# =============================================================================

# After setting up authentication, start the web UI:
# zrb serve --port 8000

# Access http://localhost:8000
# - Guest: Can only access "hello"
# - Jack: Can access "hello" and "greet"
# - Admin: Can access all tasks
