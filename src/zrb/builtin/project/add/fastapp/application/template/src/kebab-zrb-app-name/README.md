# PascalZrbAppName

PascalZrbAppName is a modular monolith application built on top of [FastApi](https://fastapi.tiangolo.com/) and [Svelte Kit](https://kit.svelte.dev/).

You can run PascalZrbAppName as a monolith or microservices.

Running your application as a monolith is preferable during local development. Furthermore, monolith application is more maintainable than microservices.

The purpose of PascalZrbAppName is to:

- Give you a sensible default.
- Give you a good experience while developing/testing things locally.
- Assure you that your application is always ready to be deployed as microservices.

You can learn more about PascalZrbAppName's modular monolith concept in our [documentation](docs/modular-monolith/README.md).

# Run PascalZrbAppName as a monolith

To run PascalZrbAppName as a monolith, you can invoke the following command:

```bash
zrb project start-kebab-zrb-app-name --kebab-zrb-app-name-run-mode monolith
```

You can also run PascalZrbAppName as a docker container by invoking the following command:

```bash
zrb project start-kebab-zrb-app-name-container --kebab-zrb-app-name-run-mode monolith
```

# Run PascalZrbAppName as a microservices

To run PascalZrbAppName as a microservices, you can invoke the following command:

```bash
zrb project start-kebab-zrb-app-name --kebab-zrb-app-name-run-mode microservices
```

You can also run PascalZrbAppName as a docker container by invoking the following command:

```bash
zrb project start-kebab-zrb-app-name-container --kebab-zrb-app-name-run-mode microservices
```

# Accessing the web interface

Once you start the application, you can visit [`http://localhost:zrbAppHttpPort`](http://localhost:zrbAppHttpPort) in your browser. By default, the application will run on port zrbAppHttpPort, but you can change the port by providing `ZRB_ENV_PREFIX_APP_PORT`.

To log in as admin, you can use the following credential:

- User: `root`
- Password: `toor`

You can change the default username and password by providing `ZRB_ENV_PREFIX_APP_AUTH_ADMIN_USERNAME` and `ZRB_ENV_PREFIX_APP_AUTH_ADMIN_PASSWORD`.

Furthermore, you can also visit `http://localhost:zrbAppHttpPort/docs` to access the API specification.

# Deploying to Kubernetes

To deploy PascalZrbAppName to Kubernetes, you need to have [Pulumi](https://www.pulumi.com/) installed. You also need access to a container registry like [Docker Hub](https://hub.docker.com/) and to the Kubernetes cluster itself.

The easiest way to set up Kubernetes on your local computer is by installing [Docker Desktop](https://www.docker.com/products/docker-desktop/). Once you installed Docker Desktop, you can go to `setting | Kubernetes` to enable your local Kubernetes cluster.

Finally, you can invoke the following command:

```bash
# Deploy PascalZrbAppName to Kubernetes as a monolith
zrb project deploy-kebab-zrb-app-name --kebab-zrb-app-name monolith

# Deploy PascalZrbAppName to Kubernetes as a microservices
zrb project deploy-kebab-zrb-app-name --kebab-zrb-app-name microservices
```

# Configuration

You can see all available configurations on [`template.env`](src/template.env). If you need to override the configuration, you can provide environment variables with `ZRB_ENV_PREFIX_` prefix to the ones specified in the `template.env`.

There are several configurations you need to know.

Auth related config

- `ZRB_ENV_PREFIX_APP_AUTH_ADMIN_ACTIVE`: determine whether there is an admin user or not
    - default value: `true`
- `ZRB_ENV_PREFIX_ADMIN_USERNAME`: Admin username
    - default value: `root`
- `ZRB_ENV_PREFIX_ADMIN_PASSWORD`: Admin password
    - default value: `toor`
- `ZRB_ENV_PREFIX_APP_PORT`: Application port
    - default value: `zrbAppHttpPort`

Messaging config:

- `ZRB_ENV_PREFIX_APP_BROKER_TYPE`: Messaging platform to be used (i.e., `rabbitmq`, `kafka`, or `mock`)
    - default value: `rabbitmq`

Feature flags:

- `ZRB_ENV_PREFIX_APP_ENABLE_EVENT_HANDLER`: Whether enable event handler or not
    - default value: `true`
- `ZRB_ENV_PREFIX_APP_ENABLE_RPC_SERVER`: Whether enable RPC server or not
    - default value: `true`
- `ZRB_ENV_PREFIX_APP_ENABLE_FRONTEND`: Whether enable Frontend or not
    - default value: `true`
- `ZRB_ENV_PREFIX_APP_ENABLE_API`: Whether enable API or not
    - default value: `true`
- `ZRB_ENV_PREFIX_APP_ENABLE_AUTH_MODULE`: Whether enable Auth module or not
    - default value: `true`
- `ZRB_ENV_PREFIX_APP_ENABLE_LOG_MODULE`: Whether enable Log module or not
    - default value: `true`
- `ZRB_ENV_PREFIX_APP_ENABLE_<MODULE_NAME>_MODULE`: Whether enable `<MODULE_NAME>` module or not
    - default value: `true`


# Adding modules, entities, or fields

There are CLI commands to help you add modules, entities, and fields into PascalZrbAppName.

For simple CRUD, you won't need to code at all. Please see [Zrb tutorial](https://github.com/state-alchemists/zrb/blob/main/docs/tutorials/development-to-deployment-low-code.md) for more details.


# Prerequisites

Main prerequisites

- Python 3.10 or higher
- Pip
- Venv
- Node version 18 or higher
- Npm

If you want to run PascalZrbAppName on containers, you will also need `Docker` with the `Docker-compose` plugin.

You will also need `Pulumi` if you want to deploy PascalZrbAppName into your Kubernetes cluster.

# Directory Structure

- `docker-compose.yml`: A multi-profile docker-compose file. This helps you to run your application as a monolith/microservices.
- `all-module-disabled.env`: Feature flags to be used when you deactivate all modules.
- `all-module-enabled.env`: Feature flags to be used when you activate all modules.
- `deployment/`: Deployment directory. By default, we put deployment along with the source code to make it easier to maintain/manage. You can later move your deployments to another repository if you think you need to.
    - `/helm-charts`: Helm charts for Rabbitmq, Redpanda, and Postgre.
    - `__main__.py`: Main Pulumi script.
    - `template.env`: Default configuration for deployment
- `src/`: PascalZrbAppName source code, including backend and frontend.
    - `Dockerfile`: Dockerfile to build PascalZrbAppName
    - `template.env`: Default configuration to run PascalZrbAppName
    - `requirements.txt`: Pip packages, list of PascalZrbAppName dependencies. If you need to use external libraries in PascalZrbAppName, make sure to list them here.
    - `main.py`: PascalZrbAppName's application entry point. This module exposes an `app` object that will be picked up by Uvicorn.
    - `config.py`: PascalZrbAppName's configuration loader.
    - `migrate.py`: A script to perform database migration.
    - `integration/`: Initialization of components you want to use in your application. Typically containing scripts to instantiate `app` objects, DB connections, Message bus connections, etc. This is where you create and connect components.
    - `component/`: Interface and component class definitions.
    - `frontend/`: Frontend source code
        - `package.json`: NPM configuration for PascalZrbAppName frontend.
        - `svelte.config.json`: Svelte configuration.
        - `tailwind.config.json`: Tailwind configuration.
        - `vite.config.ts`: Vite configuration.
        - `src/`: PascalZrbAppName frontend source code.
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
            - `integration/`: Initialization of components for the current module.
                - `model/`
                - `repo/`
            - `component/`: Interface and component class definition for the current module.
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
- PascalZrbAppName's Frontend is served as static files and is built before runtime (not SSR/Server Side Rendering). That's mean.
    - The SEO is probably not good.
    - The page load is sensibly good.
- We use Svelte for Frontend because it is easier to read/learn compared to React, Vue, or Angular.
- At the moment, the frontend use:
    - Sveltekit
    - TailwindCSS
    - DaisyUI

## Database

- PascalZrbAppName uses SQLAlchemy to handle
    - Database connection
    - Database migration
    - Data manipulation
- To create a custom database implementation, you need to create an implementation that complies with `core.repo.Repo`.

## Messaging

- Currently, PascalZrbAppName supports some messaging platforms:
    - Rabbitmq (default):
        - `APP_BROKER_TYPE=rabbitmq`
    - Kafka/Redpanda
        - `APP_BROKER_TYPE=kafka`
    - No messaging platform, a.k.a: in memory. This will only work properly if you run PascalZrbAppName as a monolith.
        - `APP_BROKER_TYPE=mock`
- To create custom event handlers, you need to implement two interfaces:
    - `core.messagebus.Publisher`
    - `core.messagebus.Server`

## RPC

- Currently, RPC implementation depends on the messaging platforms. It is possible to override this behavior by creating you custom implementation. There are two interfaces you need to override:
    - `core.rpc.Caller`
    - `core.rpc.Server`
