# PascalZrbProjectName

PascalZrbProjectName is a [Zrb](https://pypi.org/project/zrb/) project.

There are two directories in the project:

- `_automate`: This directory contains Zrb task definitions
- `src`: This directory contains all source code and resources.

To learn more about the project, you can visit [Zrb getting started page](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md).

# Prerequisites

To start working with PascalZrbProjectName, you need to have:

- Python 3.10 or higher
- Pip
- Venv

You can also use [Zrb Docker container](https://github.com/state-alchemists/zrb#-with-docker) if you prefer to work with Docker.

# Getting started

To get started, you need to activate PascalZrbProjectName virtual environment and install a few packages (including Zrb). You can do this by invoking the following command in your terminal:

```bash
source ./project.sh
```

Once the virtual environment is activated, you will be able to invoke any Zrb commands.

To make sure that Zrb is accessible, you can try to invoke the following commands:

```bash
zrb version
```

# Creating an application

You can add a new application to PascalZrbProjectName by invoking the following command:

```bash
zrb project add fastapp
```

Once the application is created, you can start it by invoking the following command:

```bash
zrb project start-<app-name>
```

You will be able to find the application under PascalZrbProjectName's `src` directory.

Zrb also allows you to create CRUD entities on your application. Please visit [Zrb's development-to-deployment tutorial](https://github.com/state-alchemists/zrb/blob/main/docs/tutorials/development-to-deployment-low-code.md) to learn more.

# Configuration

To configure PascalZrbProjectName, you need to create a `.env` file.

You can see the default configuration by invoking the following command:

```
zrb project get-default-env
```

Once the environment file is updated, you can reload PascalZrbProjectName by invoking `reload` in the terminal.
