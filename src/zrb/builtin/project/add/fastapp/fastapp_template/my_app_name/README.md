# My App Name

Welcome to My App Name! This application is designed to help you start your project with a flexible architecture that can scale as your needs grow. My App Name supports both monolithic and microservices architectures, allowing you to start small and expand without rewriting your codebase.

## Key Features

- **Modular-Monolith Architecture**: My App Name is built with a modular-monolith architecture, providing a clean interface for inter-module communication. This allows you to run My App Name as a monolith or as microservices without altering your code.

- **Low Coupling, High Cohesion**: The architecture ensures low coupling and high cohesion, making it easy to split your code into microservices when needed.

## How It Works

### Inter-Module Communication

Each module in My App Name is independent and communicates with others through a `Client` object. The `Client` is an interface with two implementations: `ApiClient` and `DirectClient`.

- **ApiClient**: Used when running My App Name as microservices. It communicates over HTTP using a base URL.
- **DirectClient**: Used when running My App Name as a monolith. It allows direct method calls between modules.

### Code Examples

Here's how you can use the `as_api_client` and `as_direct_client` methods:

```python
# Using as_api_client
from my_app_name.config import APP_AUTH_BASE_URL
from my_app_name.module.auth.service.permission.permission_service_factory import permission_service

# Create an API client for the permission service
permission_api_client = permission_service.as_api_client(base_url=APP_AUTH_BASE_URL)

# Using as_direct_client
from my_app_name.module.auth.service.role.role_service_factory import role_service

# Create a direct client for the role service
role_direct_client = role_service.as_direct_client()
```
## Application Architecture

My App Name follows a modular-monolith architecture. Each module (e.g., Auth, Library) encapsulates a specific business capability. The Gateway module acts as the entry point for user interactions (e.g., web UI).

**Communication Modes:**

1.  **Monolith (Direct Communication):**
    ```
    +---------+       +---------+
    | Gateway | ----> |  Auth   |  (e.g., for login, permission checks)
    | (UI)    |       | Service |
    +---------+       +---------+
        |                 ^
        |                 | (Library might call Auth for specific checks)
        |                 |
        v                 |
    +---------+ -----------+
    | Library |
    | Service |
    +---------+
     (Gateway also calls Library directly)
     (DirectClient calls between services if needed)
    ```
    Modules communicate directly via `DirectClient` implementations. The Gateway calls necessary services, and services can call each other directly if required.

2.  **Microservices (API Communication):**
    ```
    +---------+       +---------+
    | Gateway | ----> |  Auth   |  (e.g., via Auth API)
    | (UI)    |       | Service |
    |         |       | (API)   |
    +---------+       +---------+
        |                 ^
        |                 | (Library Service might call Auth API)
        |                 |
        v                 |
    +---------+ -----------+
    | Library |
    | Service |
    | (API)   |
    +---------+
     (Gateway also calls Library API)
     (ApiClient calls via HTTP between services if needed)
    ```
    Modules communicate via `ApiClient` implementations over HTTP/API calls. The Gateway calls necessary service APIs, and services can call each other's APIs if required.

## Factory Pattern

The application utilizes the Factory pattern extensively, particularly for creating client, service, and repository instances. This allows the application to switch between different implementations based on configuration settings.

**Example (`my_app_name/module/auth/client/auth_client_factory.py`):**

```python
from my_app_name.config import APP_COMMUNICATION
from my_app_name.module.auth.client.auth_api_client import AuthAPIClient
from my_app_name.module.auth.client.auth_client import AuthClient
from my_app_name.module.auth.client.auth_direct_client import AuthDirectClient

# Selects the client based on the configuration
if APP_COMMUNICATION == "direct":
    auth_client: AuthClient = AuthDirectClient()  # Used in Monolith mode
elif APP_COMMUNICATION == "api":
    auth_client: AuthClient = AuthAPIClient()      # Used in Microservices mode
```

By changing the `APP_COMMUNICATION` variable in `my_app_name/config.py`, you can switch how modules communicate without changing the core module logic. Similar factories exist for services and repositories (e.g., switching between database and in-memory implementations based on `APP_REPOSITORY_TYPE`).

## Key Folders and Files

-   `my_app_name/config.py`: Central configuration file (database connections, communication mode, etc.).
-   `my_app_name/main.py`: Main application entry point.
-   `my_app_name/common/`: Shared utilities, base classes (e.g., `app_factory.py`, `base_service.py`).
-   `my_app_name/module/`: Contains the application modules (e.g., `auth`, `library`, `gateway`).
    -   `my_app_name/module/<module_name>/`: Each module directory typically contains:
        -   `client/`: Client interfaces (`*_client.py`, `*_api_client.py`, `*_direct_client.py`) and factories (`*_client_factory.py`).
        -   `service/`: Business logic implementation (`*_service.py`) and factories (`*_service_factory.py`).
        -   `repository/`: Data access logic (`*_repository.py`, `*_db_repository.py`) and factories (`*_repository_factory.py`).
        -   `route.py`: API or UI routes for the module.
        -   `schema/`: Data transfer objects or database models (if applicable).
        -   `migration/`: Database migration scripts (if using Alembic).
-   `my_app_name/schema/`: Shared data schemas used across modules.
-   `my_app_name/test/`: Unit and integration tests.
-   `my_app_name/_zrb/`: Tooling scripts (likely for code generation or automation).


## Principles

- Developers should be able to override everything with a reasonable amount of code.
- Simple tasks should only require a small amount of code.
- A bit of magic is okay as long as it's transparent and documented.

For more details, refer to the client implementations in `module/auth/client/auth_api_client.py` and `module/auth/client/auth_direct_client.py`.