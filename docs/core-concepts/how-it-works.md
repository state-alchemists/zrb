🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md)

# How It Works: The Zrb Lifecycle

Understanding the Zrb lifecycle is key to mastering it. When you execute a task, Zrb follows a precise sequence of steps to manage dependencies, gather inputs, and run your code. This document walks you through that journey, from command-line invocation to task completion.

## The Big Picture

This diagram illustrates the detailed workflow when you run a task.

```mermaid
graph TD
    subgraph A["Step 1: Initiation"]
        A1(zrb my-task --input="val") --> A2{CLI Runner};
    end

    subgraph B["Step 2: Session Setup"]
        A2 --> B1(Create Session);
        B1 --> B2(Create Shared Context);
        B1 --> B3(Parse CLI args);
        B2 & B3 --> B4(Populate Context with Inputs);
    end

    subgraph C["Step 3: Task Execution"]
        B1 --> C1{task.run()};
        C1 --> C2{For each 'upstream' task};
        C2 --> C3(Run upstream task);
        C3 --> C2;
        C2 --> C4{Task is Ready};
    end

    subgraph D["Step 4: Action"]
        C4 --> D1(Run Readiness Checks);
        D1 --> D2(Populate Task-Specific Env/Inputs);
        D2 --> D3(Execute 'action');
    end

    subgraph E["Step 5: Completion"]
        D3 -- Success --> E1(Run 'successor' tasks);
        D3 -- Failure --> E2(Run 'fallback' tasks);
    end
```

## The Step-by-Step Breakdown

### Step 1: Initiation (The Runner)

Everything begins when you type a command in your terminal.

1.  **Command Execution**: You run a command like `zrb my-group my-task --name="Zaruba"`.
2.  **Runner Takes Over**: The `Cli` runner in `zrb` is activated. It parses your command to identify the target task (`my-task`) and any command-line arguments (`--name="Zaruba"`).

### Step 2: Session and Context Setup

Before any task logic runs, Zrb prepares the environment.

1.  **Session Created**: A `Session` object is instantiated. This object represents the entire lifecycle of this specific command execution and will manage all the tasks involved.
2.  **Shared Context Created**: A `SharedContext` is created and attached to the session. This context will hold all the state that is shared across tasks, including inputs, environment variables, and data passed via `XCom`.
3.  **Inputs are Parsed**: The runner processes the command-line arguments you provided. Any arguments that match the `Input`s defined for the target task (and its dependencies) are loaded into the `SharedContext`.

### Step 3: Task Execution and Dependency Resolution

Now Zrb turns its attention to the task itself.

1.  **`task.run()` is Called**: The runner invokes the `run()` method on the target `my-task`.
2.  **Upstream First**: Before `my-task` can run, it must honor its dependencies. Zrb looks at the `upstream` list (and any tasks added with the `>>` operator). It recursively calls `run()` on each of those upstream tasks first. This ensures that dependencies are always executed before the tasks that depend on them.
3.  **Interactive Inputs**: As each task is about to run, Zrb checks if all its required `Input`s have a value in the `SharedContext`. If a value is missing, Zrb automatically prompts you to enter it on the command line.

### Step 4: The Action

Once all dependencies are met, the task's main logic is executed.

1.  **Readiness Checks**: If the task has any `readiness_check` tasks defined, they are executed now. The main action will not proceed until all readiness checks pass. This is crucial for waiting for services like databases or web servers to start up.
2.  **Environment Population**: The task's `Env` definitions are processed. Zrb collects variables from OS environment, `.env` files, and defaults, making them available in the task's `Context`.
3.  **Action is Executed**: The core `action` of the task (e.g., a shell command or a Python function) is finally executed. It receives a `Context` object, giving it access to all the resolved inputs (`ctx.input`) and environment variables (`ctx.env`).

### Step 5: Completion and Follow-up

After the action completes, Zrb handles the outcome.

1.  **Return Value to XCom**: If the action returns a value, that value is automatically pushed to an `XCom` queue named after the task, making it available to other tasks.
2.  **Successors or Fallbacks**:
    *   If the task's action was **successful**, any `successor` tasks are executed.
    *   If the action **failed**, any `fallback` tasks are executed, allowing for robust error handling and cleanup operations.

This structured lifecycle ensures that your automations are predictable, resilient, and easy to debug.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md)

➡️ [Next: Task](./task/README.md)
