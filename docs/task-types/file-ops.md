🔖 [Documentation Home](../../README.md) > [Task Types](./) > File Operations

# File Operations

Zrb provides specialized tasks for manipulating and synchronizing the filesystem.

---

## Table of Contents

- [`Scaffolder`](#1-scaffolder)
- [`RsyncTask`](#2-rsynctask)
- [Quick Comparison](#quick-comparison)

---

## 1. `Scaffolder`

The `Scaffolder` task is a powerful templating engine. It copies an entire directory structure from a source to a destination, performing find-and-replace text transformations on the file contents **and even the filenames themselves**.

### When to Use

| Use Case | Description |
|----------|-------------|
| Project scaffolding | Create "new project" wizards |
| Boilerplate generation | Generate standardized code modules |
| Configuration templates | Establish team-wide config standards |

### Example

Imagine you have a template directory at `./templates/basic-app`. You want to copy it to a new location and replace the word `APP_NAME_PLACEHOLDER` with a user-provided name.

```python
from zrb import Scaffolder, StrInput, cli

create_project = cli.add_task(
    Scaffolder(
        name="create-project",
        input=StrInput(name="project_name", description="Name of the app"),
        
        # The directory containing your template files
        source_path="./templates/basic-app",
        
        # The destination path (renders {ctx.x} placeholders from inputs)
        destination_path="./projects/{ctx.input.project_name}",
        
        # A dictionary of strings to find and replace in the copied files
        transform_content={
            "APP_NAME_PLACEHOLDER": "{ctx.input.project_name}"
        }
    )
)
```

When a user runs `zrb create-project --project-name my-cool-app`, Zrb creates the new directory and injects `my-cool-app` wherever the placeholder existed in the templates.

### Per-File Transforms with `ContentTransformer`

The dict shorthand above rewrites every copied file the same way. To limit a
transform to specific files, pass `ContentTransformer` instance(s) to
`transform_content` instead of a dict:

```python
from zrb import ContentTransformer, Scaffolder, StrInput, cli

create_project = cli.add_task(
    Scaffolder(
        name="create-project",
        input=StrInput(name="project_name", description="Name of the app"),
        source_path="./templates/basic-app",
        destination_path="./projects/{ctx.input.project_name}",
        transform_content=[
            ContentTransformer(
                name="rename-app",
                match="*.py",  # glob, matched against each file's basename
                transform={"APP_NAME_PLACEHOLDER": "{ctx.input.project_name}"},
            ),
        ],
    )
)
```

`match` accepts a glob, a list of globs, or a predicate `(ctx, file_path) -> bool`.
By default (`match_mode="auto"`) a string pattern is tried as a regex first and
falls back to a glob — so a glob-shaped pattern that also happens to parse as a
valid regex is matched with regex semantics (e.g. `"config.json"` also matches
`"configXjson"`, since `.` is a regex wildcard). Pass `match_mode="glob"` to
force plain glob matching, or `match_mode="regex"` to force regex-only.

---

## 2. `RsyncTask`

The `RsyncTask` provides a strongly-typed Python interface over the battle-tested `rsync` command-line utility. It handles complex synchronization between local folders or remote servers via SSH.

### When to Use

| Use Case | Description |
|----------|-------------|
| Backups | Sync local folders |
| Mirror deployments | Deploy to remote servers |
| Artifact sync | Transfer build outputs |

### Local to Local Sync

```python
from zrb import RsyncTask, cli

sync_local = cli.add_task(
    RsyncTask(
        name="backup-data",
        local_source_path="./data/",
        local_destination_path="./backup/data/",
    )
)
```

### Local to Remote Sync (Push via SSH)

You can sync files directly to a remote server. While SSH keys are the recommended authentication method, `RsyncTask` also supports password authentication.

```python
from zrb import RsyncTask, cli

deploy_remote = cli.add_task(
    RsyncTask(
        name="deploy",
        local_source_path="./dist/",
        remote_host="prod.example.com",
        remote_user="deploy_user",
        remote_destination_path="/var/www/html/",
        
        # Optional advanced configurations
        remote_port=2222,
        exclude_from=".rsyncignore",
        
        # Password auth: read the real secret from an env var via zrb's
        # templating, and pass it through the `remote_password` kwarg.
        # Zrb injects it as the `SSHPASS` env var and shells out via
        # `sshpass -e` under the hood.
        remote_password="{env.MY_SSH_PASSWORD}"
    )
)
```

---

## Quick Comparison

| Feature | `Scaffolder` | `RsyncTask` |
|---------|--------------|-------------|
| **Purpose** | Template generation | File synchronization |
| **Direction** | Source → Destination (one-way) | Bidirectional or one-way |
| **Transformations** | Yes (find/replace) | No (exact copy) |
| **Remote support** | No | Yes (via SSH) |
| **Best for** | New projects, boilerplate | Backups, deployments |

---

🔖 [Documentation Home](../../README.md) > [Task Types](./) > File Operations
