# PascalAppName

PascalAppName is a modular monolith application built on top of [FastApi](https://fastapi.tiangolo.com/) and [Svelte Kit](https://kit.svelte.dev/).

You can run PascalAppName as a monolith or microservices.

Running your application as a monolith is preferable during local development. Furthermore, monolith application is more maintainable than microservices.

The purpose of PascalAppName is to:

- Give you a sensible default.
- Give you a good experience while developing/testing things locally.
- Assure you that your application is always ready to be deployed as microservices.

You can learn more about PascalAppName's modular monolith concept in our [documentation](docs/modular-monolith/README.md).

# Run PascalAppName as a monolith

To run PascalAppName as a monolith, you can invoke the following command:

```bash
zrb project start-kebab-app-name --kebab-app-name-run-mode monolith
```

You can also run PascalAppName as a docker container by invoking the following command:

```bash
zrb project start-kebab-app-name-container --kebab-app-name-run-mode monolith
```

# Run PascalAppName as a microservices

To run PascalAppName as a microservices, you can invoke the following command:

```bash
zrb project start-kebab-app-name --kebab-app-name-run-mode microservices
```

You can also run PascalAppName as a docker container by invoking the following command:

```bash
zrb project start-kebab-app-name-container --kebab-app-name-run-mode microservices
```

# Accessing the web interface

Once you start the application, you can visit [`http://localhost:appHttpPort`](http://localhost:appHttpPort) in your browser. By default, the application will run on port appHttpPort, but you can change the port by providing `ENV_PREFIX_APP_PORT`.

To log in as admin, you can use the following credential:

- User: `root`
- Password: `toor`

You can change the default username and password by providing `ENV_PREFIX_APP_AUTH_ADMIN_USERNAME` and `ENV_PREFIX_APP_AUTH_ADMIN_PASSWORD`.

Furthermore, you can also visit `http://localhost:appHttpPort/docs` to access the API specification.

# Deploying to Kubernetes

To deploy PascalAppName to Kubernetes, you need to have [Pulumi](https://www.pulumi.com/) installed. You also need access to a container registry like [Docker Hub](https://hub.docker.com/) and to the Kubernetes cluster itself.

The easiest way to set up Kubernetes on your local computer is by installing [Docker Desktop](https://www.docker.com/products/docker-desktop/). Once you installed Docker Desktop, you can go to `setting | Kubernetes` to enable your local Kubernetes cluster.

Finally, you can invoke the following command:

```bash
# Deploy PascalAppName to Kubernetes as a monolith
zrb project deploy-kebab-app-name --kebab-app-name monolith

# Deploy PascalAppName to Kubernetes as a microservices
zrb project deploy-kebab-app-name --kebab-app-name microservices
```

# Configuration

You can see all available configurations on [`template.env`](src/template.env). If you need to override the configuration, you can provide environment variables with `ENV_PREFIX_` prefix to the ones specified in the `template.env`.

There are several configurations you need to know.

Auth related config

- `ENV_PREFIX_APP_AUTH_ADMIN_ACTIVE`: determine whether there is an admin user or not
    - default value: `true`
- `ENV_PREFIX_ADMIN_USERNAME`: Admin username
    - default value: `root`
- `ENV_PREFIX_ADMIN_PASSWORD`: Admin password
    - default value: `toor`
- `ENV_PREFIX_APP_PORT`: Application port
    - default value: `appHttpPort`

Messaging config:

- `ENV_PREFIX_APP_BROKER_TYPE`: Messaging platform to be used (i.e., `rabbitmq`, `kafka`, or `mock`)
    - default value: `rabbitmq`

Feature flags:

- `ENV_PREFIX_APP_ENABLE_EVENT_HANDLER`: Whether enable event handler or not
    - default value: `true`
- `ENV_PREFIX_APP_ENABLE_RPC_SERVER`: Whether enable RPC server or not
    - default value: `true`
- `ENV_PREFIX_APP_ENABLE_FRONTEND`: Whether enable Frontend or not
    - default value: `true`
- `ENV_PREFIX_APP_ENABLE_API`: Whether enable API or not
    - default value: `true`
- `ENV_PREFIX_APP_ENABLE_AUTH_MODULE`: Whether enable Auth module or not
    - default value: `true`
- `ENV_PREFIX_APP_ENABLE_LOG_MODULE`: Whether enable Log module or not
    - default value: `true`
- `ENV_PREFIX_APP_ENABLE_<MODULE_NAME>_MODULE`: Whether enable `<MODULE_NAME>` module or not
    - default value: `true`


# Adding modules, entities, or fields

There are CLI commands to help you add modules, entities, and fields into PascalAppName.

For simple CRUD, you won't need to code at all. Please see [Zrb tutorial](https://github.com/state-alchemists/zrb/blob/main/docs/tutorials/development-to-deployment-low-code.md) for more details.


# Prerequisites

Main prerequisites

- Python 3.9 or higher
- Pip
- Venv
- Node version 18 or higher
- Npm

If you want to run PascalAppName on containers, you will also need `Docker` with the `Docker-compose` plugin.

You will also need `Pulumi` if you want to deploy PascalAppName into your Kubernetes cluster.

# Directory Structure

- `docker-compose.yml`: A multi-profile docker-compose file. This helps you to run your application as a monolith/microservices.
- `all-module-disabled.env`: Feature flags to be used when you deactivate all modules.
- `all-module-enabled.env`: Feature flags to be used when you activate all modules.
- `deployment/`: Deployment directory. By default, we put deployment along with the source code to make it easier to maintain/manage. You can later move your deployments to another repository if you think you need to.
    - `/helm-charts`: Helm charts for Rabbitmq, Redpanda, and Postgre.
    - `__main__.py`: Main Pulumi script.
    - `template.env`: Default configuration for deployment
- `src/`: PascalAppName source code, including backend and frontend.
    - `Dockerfile`: Dockerfile to build PascalAppName
    - `template.env`: Default configuration to run PascalAppName
    - `requirements.txt`: Pip packages, list of PascalAppName dependencies. If you need to use external libraries in PascalAppName, make sure to list them here.
    - `main.py`: PascalAppName's application entry point. This module exposes an `app` object that will be picked up by Uvicorn.
    - `config.py`: PascalAppName's configuration loader.
    - `migrate.py`: A script to perform database migration.
    - `component/`: Definition of components you want to use in your application. Typically containing scripts to instantiate `app` objects, DB connections, Message bus connections, etc. This is where you create and connect components.
    - `core/`: Interface and component class definitions.
    - `frontend/`: Frontend source code
        - `package.json`: NPM configuration for PascalAppName frontend.
        - `svelte.config.json`: Svelte configuration.
        - `tailwind.config.json`: Tailwind configuration.
        - `vite.config.ts`: Vite configuration.
        - `src/`: PascalAppName frontend source code.
            - `lib/`: Frontend components and helpers.
            - `routes/`: Frontend page definitions.
        - `build/`: Frontend build result.
        - `static/`: Static files like images, favicon, etc.
    - `helper/`: Common helper scripts. Typically stateless.
    - `schema/`: Common Pydantic schemas. 
    - `module/`: Module definition. Each module can be deployed as a microservice. Thus, modules should be isolated from each other.
        - `<module_name>/`: Module resources.
            - `api.py`: HTTP request handler for the current module.
            - `event.py`: Event handler for the current module.
            - `rpc.py`: RPC handler for the current module.
            - `register_module.py`: A script to register the module to the main application.
            - `migrate.py`: A script to perform migration for the current module.
            - `component/`: Component objects for the current module.
                - `model/`
                - `repo/`
            - `core/`: Interface and component class definition for the current module.
            - `entity/`: Entity related resources.
                - `<entity_name>/`: Resources for current entity.
                    - `api.py`
                    - `rpc.py`
                    - `model.py`
                    - `repo.py`
            - `schema/`: Pydantic schemas for the current module.
- `test/`: Test scripts.
    - `<modules-name>/`: Test scripts for modules.
    - `test_*.py`: Core test scripts.


# Decisions and Constraints

## Frontend
- PascalAppName's Frontend is served as static files and is built before runtime (not SSR/Server Side Rendering). That's mean.
    - The SEO is probably not good.
    - The page load is sensibly good.
- We use Svelte for Frontend because it is easier to read/learn compared to React, Vue, or Angular.
- At the moment, the frontend use:
    - Sveltekit
    - TailwindCSS
    - DaisyUI

## Database

- PascalAppName uses SQLAlchemy to handle
    - Database connection
    - Database migration
    - Data manipulation
- To create a custom database implementation, you need to create an implementation that complies with `core.repo.Repo`.

## Messaging

- Currently, PascalAppName supports some messaging platforms:
    - Rabbitmq (default):
        - `APP_BROKER_TYPE=rabbitmq`
    - Kafka/Redpanda
        - `APP_BROKER_TYPE=kafka`
    - No messaging platform, a.k.a: in memory. This will only work properly if you run PascalAppName as a monolith.
        - `APP_BROKER_TYPE=mock`
- To create custom event handlers, you need to implement two interfaces:
    - `core.messagebus.Publisher`
    - `core.messagebus.Server`

## RPC

- Currently, RPC implementation depends on the messaging platforms. It is possible to override this behavior by creating you custom implementation. There are two interfaces you need to override:
    - `core.rpc.Caller`
    - `core.rpc.Server`
