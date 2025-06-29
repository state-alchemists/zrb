🔖 [Home](../../README.md)
# Zrb Documentation

Welcome to the official documentation for Zrb, your automation powerhouse!

Zrb is a powerful and flexible tool designed to help you automate repetitive tasks, integrate with modern technologies like Large Language Models (LLMs), and build custom workflows using Python. Whether you are a beginner looking to automate simple scripts or an experienced developer building complex CI/CD pipelines, Zrb provides the tools and structure you need.

This documentation is your starting point to learn more about Zrb, understand its core concepts, and explore its capabilities.

## Table of Contents

* [Installation and Configuration](./installation-and-configuration/README.md)

*   [Introduction](#introduction)
*   [Why Zrb?](#why-zrb)
*   [Key Features](#key-features)
*   [Getting Started](#getting-started)
    *   [Installation](#installation)
    *   [Quick Start](#quick-start)
    *   [Android Setup](./android_setup.md)
*   [Core Concepts](#core-concepts)
    *   [Tasks](#tasks)
    *   [Groups](#groups)
    *   [CLI](#cli)
    *   [Context](#context)
    *   [Session](#session)
    *   [Inputs](#inputs)
    *   [Environment Variables](#environment-variables)
    *   [XCom](#xcom)
    [Configuration](./configuration.md)
*   [Advanced Topics](#advanced-topics)
    *   [CI/CD Integration](./ci_cd.md)
    *   [Upgrading Guide 0.x.x to 1.x.x](./upgrading_guide_0_to_1.md)
    *   [Troubleshooting](./troubleshooting/)
    *   [Maintainer Guide](./maintainer-guide.md)
    *   [Changelog](./changelog.md)
    *   [Creating a Custom Zrb Powered CLI](./creating-custom-zrb-powered-cli.md)
*   [Demo & Community](#demo--community)

### Quick Start

Dive right in and build a simple automation workflow with two tasks: one using an LLM and another executing a command. This guide will walk you through creating your `zrb_init.py` file and running your tasks.

Start the Quick Start guide: [Build Your First Automation Workflow](./task/creating_tasks.md)

## Core Concepts

Understanding these core concepts is key to effectively using Zrb.

### Tasks

Tasks are the fundamental units of work in Zrb. Each task represents a specific action or step in your automation workflow. Tasks can be defined using Python classes or functions and can have inputs, environment variables, dependencies, and actions.

*   [Overview of Tasks](./task/README.md)
*   [Creating Tasks](./task/creating_tasks.md)
*   [Key Components of a Task](./task/key_components.md)
*   [Built-in Task Types](./task/types/README.md) (Includes links to `CmdTask`, `LLMTask`, `Scaffolder`, etc.)

### Groups

Groups allow you to organize related tasks and subgroups into a hierarchical structure. This helps manage complexity in larger projects and provides a logical way to access tasks via the CLI or web interface.

*   [Documentation on Groups](./group.md)

### CLI

The Command-Line Interface is the primary way to interact with Zrb from your terminal. You can list available tasks and groups, run specific tasks, and provide inputs and configuration via command-line arguments and environment variables.

*   [Documentation on the CLI](./cli.md)

### Context

The `Context` object (`ctx`) is passed to the `action` method of every task. It provides access to all the information a task needs during execution, including inputs, environment variables, shared session data, logging utilities, and rendering capabilities.

*   [Documentation on Context](./context.md)

### Session

A Session represents a single execution run of one or more Zrb tasks. It manages the task lifecycle, dependency resolution, context provisioning, and state logging for the entire workflow triggered by a single command or web request.

*   [Documentation on Sessions](./session.md)

### Inputs

Inputs are used to pass parameters to your tasks. You can define various types of inputs (string, integer, boolean, options) with default values and descriptions. Zrb handles prompting the user for input if not provided via the command line or other means.

*   [Documentation on Inputs](./input.md)

### Environment Variables

Environment variables are used for configuration. Zrb allows you to define environment variables for tasks, load them from `.env` files, and link them to system environment variables. These are accessible via the `ctx.env` object.

*   [Documentation on Environment Variables](./env.md)

### XCom

XCom (Cross-Communication) is a mechanism for tasks to exchange small amounts of data. Tasks can push data to their XCom queue, and downstream tasks can pull data from the XCom queues of their upstream dependencies.

*   [Documentation on XCom](./xcom.md)

## Advanced Topics

Once you are familiar with the core concepts, explore these guides for more advanced use cases and configuration options.

*   **Configuration:** Learn how to configure Zrb's behavior using various environment variables.
    *   [Detailed Configuration Guide](./configuration.md)
*   **CI/CD Integration:** Integrate your Zrb tasks into popular CI/CD platforms like GitHub Actions and GitLab CI using the official Zrb Docker image.
    *   [CI/CD Integration Guide](./ci_cd.md)
*   **Upgrading:** If you are migrating from an older version of Zrb (0.x.x), this guide details the key changes and how to update your task definitions.
    *   [Upgrading Guide from 0.x.x to 1.x.x](./upgrading_guide_0_to_1.md)
*   **Troubleshooting:** Find solutions and tips for common issues you might encounter.
    *   [Troubleshooting Guides](./troubleshooting/)
*   **Maintainer Guide:** Information for those interested in contributing to the Zrb project.
    *   [Maintainer Guide](./maintainer-guide.md)
*   **Changelog:** Review the changes and new features introduced in each Zrb release.
    *   [Changelog](./changelog.md)

## Demo & Community

*   **Video Demo:** See a quick demonstration of Zrb's capabilities.
    *   [![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)
*   **Community & Support:** Join the Zrb community, ask questions, report bugs, or contribute to the project.
    *   Report issues or suggest features on [GitHub Issues](https://github.com/state-alchemists/zrb/issues).
    *   Submit code changes via [GitHub Pull Requests](https://github.com/state-alchemists/zrb/pulls).
